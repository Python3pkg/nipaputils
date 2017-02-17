import sys
import urllib2
import logging
import pynipap
from pynipap import VRF, Pool, Prefix, AuthOptions, NipapError
import constants as CONSTANTS
import pg8000

"""
    NipapUtils.py - a set utility functions for working with NIPAP OpenSourc IPAM
    This also contains calls to an additional table created in NIPAP to support VLANs

"""
__author__ = "john.mcmanus@centurylink.com"


class NipapUtils(object):

    nipap_user = CONSTANTS.NIPAP_USER
    nipap_password = CONSTANTS.NIPAP_PASSWORD
    nipap_host = CONSTANTS.NIPAP_HOST
    nipap_port = CONSTANTS.NIPAP_PORT
    nipap_uri = CONSTANTS.NIPAP_URL
    conn = None


    def __init__(self):

        # setup logging
        logging.basicConfig(format='%(asctime)s %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p',
                            filename='/tmp/NipapUtils.log', level=logging.DEBUG)
        logging.debug('Initializing connection to nipap server %s' % NipapUtils.nipap_uri)

        # a bad connection string does not result in an exception
        # check to host to do some minimal amount to verification
        try:
            response = urllib2.urlopen("http://" + NipapUtils.nipap_host, timeout=10)
        except urllib2.URLError:
            logging.error("Cannot connect to nipap url %s" % NipapUtils.nipap_host)
            raise pynipap.NipapAuthError

        pynipap.xmlrpc_uri = NipapUtils.nipap_uri
        a = AuthOptions({
            'authoritative_source': CONSTANTS.NIPAP_CLIENT_NAME,
        })


    def create_nipap_db_connection(self):

        try:
            NipapUtils.conn = pg8000.connect(user=CONSTANTS.NIPAP_DB_USER, host=CONSTANTS.NIPAP_HOST,
                                       port=CONSTANTS.NIPAP_DB_PORT, database=CONSTANTS.NIPAP_DB,
                                       password=CONSTANTS.NIPAP_DB_PASSWORD)
        except Exception as e:
            logging.error("Cannot connect to nipap db url {}".format(CONSTANTS.NIPAP_HOST))

    def queryVlanByIdPort(self, vlanid, porttype):

        self.create_nipap_db_connection()
        cur = self.conn.cursor()
        try:
            cur.execute(
                "SELECT * FROM psb_vlan WHERE vlanid = (%s) and porttype = (%s);",
                (vlanid, porttype))
            rowcount = cur.rowcount
            if rowcount == -1:
                return None
            return cur.fetchall()
        except Exception as e:
            logging.error(e.message)
            cur.close()
            self.conn.close()
            raise Exception(e.message)

    def insertVlan(self, vlanid, siteid, cug, enterprisename, porttype):

        self.create_nipap_db_connection()
        cur = self.conn.cursor()
        try:
            cur.execute(
                "INSERT INTO psb_vlan (vlanid, siteid, cug, enterprisename, porttype) "
                "VALUES ((%s), (%s), (%s), (%s), (%s));",
                (vlanid, siteid, cug, enterprisename, porttype))
            rowcount = cur.rowcount
            assert rowcount is 1
            self.conn.commit()
            return True
        except Exception as e:
            logging.error(e.message)
            cur.close()
            self.conn.close()
            raise Exception(e.message)

    def deleteVlan(self, vlanid, porttype):
        try:
            cur = self.conn.cursor()
            cur.execute(
                "DELETE FROM psb_vlan WHERE vlanid = (%s) and porttype = (%s)",
                (vlanid, porttype))
            rowcount = cur.rowcount
            assert rowcount is 1
            self.conn.commit()
            return True
        except Exception as e:
            logging.error(e)
            cur.close()
            self.conn.close()
            raise Exception(e)

    def find_prefix(self, rt, prefix):
        """
        Find a prefix for a given route target (VRF)
        :param rt: string such as '1.1.1.0/24'
        :param prefix: string such as '1.1.1.0/24'
        :return: a Prefix object or None
        """
        retVal = None
        try:
            # retVal = VRF.search({'val1': 'id', 'operator': 'equals', 'val2': '10'})['result'][0]
            retVal = Prefix.search({'val1': 'prefix', 'operator': 'equals', 'val2': prefix})
            if not retVal['result']:
                retVal = None
                return retVal
            for myPrefix in retVal['result']:
                if myPrefix.vrf.rt == rt:
                    return myPrefix
        except:
            e = sys.exc_info()[0]
            logging.error("Error: could not find prefix: %s" % e)
            retVal = None
        return retVal

    def find_free_prefix(self, rt, fromprefix, prefixlength):
        """
        Note: this method simply finds the next free prefix, it does not reserve it
        :param rt: String like '209:123'
        :param fromprefix: String like '1.1.1.0/29'
        :param prefixlength: String like '32'
        :return: Prefix object or none
        """
        retVal = None
        myVrf = None
        try:
            myVrf = self.find_vrf('rt', rt)
        except:
            e = sys.exc_info()[0]
            logging.error("Error: could not find prefix: %s" % e)
            retVal = None
            return retVal

        if myVrf:
            retVal = Prefix.find_free(myVrf, {'from-prefix': [fromprefix], 'prefix_length': prefixlength})
        else:
            retVal = None

        return retVal

    def add_prefix_to_vrf(self, vrfrt, prefix, type, description, status, tags=[]):
        """
        Note: This function adds a prefix to a given VRF, if the prefix is used or
        invalid, it will return None
        :param vrfrt: String like "209:123"
        :param prefix: String like "1.0.0.0/29"
        :param type: String, must be on of the following: 'reservation', 'assignment', 'host'
        :param description: String
        :param status: String, must be "assigned" or "reserved"
        :param tags: Array of Strings
        :return: Prefix object or None
        """
        myvrf = None
        p = None

        # get the vrf
        myvrf = self.find_vrf('rt', vrfrt)
        p = Prefix()
        p.prefix = prefix
        p.type = type
        p.status = status
        p.description = description
        p.vrf = myvrf
        p.tags = tags

        try:
            p.save()
        except:
            e = sys.exc_info()[0]
            logging.error("Error: could not add prefix: %s" % e)
        return p

    def find_and_reserve_prefix(self, vrfrt, fromprefix, prefixlength, type, description, status):
        """
        Note: This function finds the next prefix and reserves it
        :param vrfrt: string representing the VRF such as '209:9999'
        :param fromprefix: string representing the CIDR such as '1.1.1.0/29'
        :param prefixlength: integer such as 32
        :param description: string displayed by nipap under prefix screen
        :return:
        """

        myPrefix = None

        freePrefix = self.find_free_prefix(vrfrt, fromprefix, prefixlength)
        if not freePrefix:
            logging.debug(
                "No prefixes available for rt %s from prefix %s with lenght %s " % vrfrt % fromprefix % prefixlength)
            return myPrefix

        # i found the next ip, now i need to actually reserve it
        # first the vrf instance needed
        vrfInst = self.find_vrf('rt', vrfrt)
        if vrfInst:
            try:
                myPrefix = myReservedPrefix = self.add_prefix("1.1.1.6/32", type, description, status, vrfInst)
            except:
                e = sys.exc_info()[0]
                logging.error("Error: could not add prefix: %s" % e)
        else:
            logging.debug("Could not find vrf %s " % vrfrt)

        return myPrefix

    def add_prefix_from_pool(self, pool, family, description):
        p = Prefix()
        args = {}
        args['from-pool'] = pool
        args['family'] = family
        p.type = pool.default_type
        p.status = 'assigned'
        try:
            p.save(args)
            return p
        except NipapError, exc:
            print "Error: could not add prefix: %s" % str(exc)
            return None

    def get_prefixs(self, name=''):
        """
        Return a prefix with the passed in name
        :param name: prefix name such as '1.1.1.0/32'
        :return: Prefix object list
        """
        if len(name) > 0:
            pass
        else:
            p = Prefix.list()
        return p

    def delete_prefix(self):
        pass

    def add_pool(self, name, description, default_type, ipv4_default_prefix_length):
        pool = Pool()
        pool.name = name
        pool.description = description
        pool.default_type = default_type
        pool.ipv4_default_prefix_length = ipv4_default_prefix_length
        try:
            pool.save()
            return pool
        except NipapError, exc:
            print "Error: could not add pool to NIPAP: %s" % str(exc)
            return None

    def delete_pool(self, name):
        if len(name) > 0:
            pool = Pool.list({"name": name})
            try:
                pool.remove()
            except NipapError, exc:
                print "Error: could not remove pool: %s" % str(exc)

    def get_pools(self, name=''):
        if len(name) > 0:
            pools = Pool.list({"name": name})
        else:
            pools = Pool.list()
        return pools

    # ****************************************
    # VRF Functions
    # ****************************************
    def add_vrf(self, name, rt, description, tags=[]):

        try:
            vrf = VRF()
            vrf.rt = rt
            vrf.name = name
            vrf.description = description
            vrf.tags = tags
            vrf.save()
            return vrf
        except NipapError, exc:
            print "Error: could not add vrf to NIPAP: %s" % str(exc)
            return None

    def delete_vrf(self, rt=None, name=None):
        """
        Deletes a vrf given the rt or name, does not work if the vrf has a prefix
        :param rt: the route target
        :param name: the VRF name
        :return: VRF object deleted
        """
        if rt is not None:
            myVRF = self.find_vrf('rt', rt)
            if myVRF is not None:
                myVRF.remove()
        elif name is not None:
            myVRF = self.find_vrf('name', name)
            if myVRF is not None:
                myVRF.remove()
        return myVRF

    def find_vrf(self, property, value):
        """
        Find an exact match for a VRF based on property such as rt "209:123", description
        :param property:
        :param value:
        :return: a VRF instance
        """

        retVal = None
        try:
            retVal = VRF.search({'val1': property, 'operator': 'equals', 'val2': value})['result'][0]
        except (KeyError, IndexError):
            retVal = None
        return retVal

    def search_vrf(self, rt):
        """
        This method wildcard searches a vrf, for example seaching for
        209:123 will return 209:123, 209:123xxxx
        :param rt:
        :return: a vrf instance
        """
        try:
            retVal = VRF.smart_search(rt)
        except:
            logging.debug("Exception search for vrf {0}".format(rt))
            retVal = None

        return retVal

    def get_ipam_ip(self, site, rt, prefix, length, type, status, description, tags=[]):
        """

        :param site: String site identifier like SC8 or DC2
        :param rt: String identifying the route target aka '209:123'
        :param prefix: String identifying the parent network  '10.173.129.0/24'
        :param length: the CIDR you want to reserve like 29 or 32
        :param type: String that must be "reservation", "assignment" or "host"
        :param status: String that must be either "assigned" or "reserved"
        :param description: String description of the ip
        :param tags: List of tags for use in query
        :return: None or the Prefix object
        """

        try:
            logging.debug("Enter function get_ipam_ip: site={} prefix={} length={} type={} status={}".format(site,
                                                                                                             prefix, length,
                                                                                                   type, status))

            retVal = self.find_and_reserve_prefix(rt, prefix, length, type, description, status)

            # add /24
            self.add_prefix_to_vrf(rt, prefix, type, description, status, tags)
        except Exception as e:
            logging.error("Error: {} could not reserve prefix {} for rt {}".format(e.message, prefix, rt))
            raise Exception("Error: {} could not reserve prefix {} for rt {}".format(e.message, prefix, rt))
        return retVal



    def get_ipam_ip_24(self, site, rt, prefix, type, status, description, tags=[]):
        """
        This is designed to add the parent network under the VRF, usually a /24
        :param site: String site identifier like SC8 or DC2
        :param rt: String identifying the route target aka '209:123'
        :param prefix: String identifying the parent network  '10.173.129.0/24'
        :param length: the CIDR you want to reserve like 29 or 32
        :param type: String that must be "reservation", "assignment" or "host"
        :param status: String that must be either "assigned" or "reserved"
        :param description: String description of the ip
        :param tags: List of tags for use in query
        :return: None or the Prefix object
        """

        try:
            logging.debug(
                "Enter function get_ipam_ip_24: site={} rt={} prefix={} type={} status={}".format(site,
                                                                                                  rt, prefix,
                                                                                                  type, status))
            retVal = self.add_prefix_to_vrf(rt, prefix, type, description, status, tags)
        except:
            e = sys.exc_info()[0]
            logging.debug("Error: {} could not reserve prefix {} for rt {}".format(e, prefix, rt))
        return retVal

if __name__ == '__main__':

    '''
    Examples calls are below, Note normally exceptions would be caught here with appropriate errors
    In this case, this is just example code. A VRF represents a Virtual Private Routed Network (VPRN)
    identifier in Alcatel Lucent or Nokia terminology. VRF is the cisco term, same thing.
    '''

    # createNipapClient()
    # pool1 = NipapUtils.add_pool('test', 'assignment', 31, 112)

    # list the pools

    this = NipapUtils()
    this.get_pools()

    # add a pool with /29 as a CIDR
    this.add_pool("Techdiverdown Pool", "Test Pool", "assignment", 29)

    #### VRF Stuff ###

    # get a specific VRF, RT is route target
    vrfs = this.get_vrfs('RT 4444')
    for vrf in vrfs:
        print "Getting one specific VRF"
        print vrf.rt, vrf.description, vrf.name

    # get all VRFs
    vrfs = this.get_vrfs()
    for vrf in vrfs:
        print "Getting all VRFS"
        print vrf.rt, vrf.description, vrf.name

    # add a VRF, 2nd param is the AS:VPRN  see here: https://www.apnic.net/get-ip/faqs/asn
    vrf = this.add_vrf("MY VRF", "123:7654", "VRF Test")