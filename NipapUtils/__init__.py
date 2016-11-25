import sys
import urllib3
import logging
import pynipap
from pynipap import VRF, Pool, Prefix, AuthOptions, NipapError

"""
    NipapUtils.py - a set utility functions for working with NIPAP
"""
__author__ = "techdiverdown@gmail.com"


class NipapUtils:
    # replace with your nipap username used during install
    nipap_user = 'myuser'
    # replace with your nipap password
    nipap_password = 'mypassword'
    # replace with your url
    nipap_host = 'myhostname'
    nipap_port = '1337'
    nipap_uri = "http://" + nipap_user + ":" + nipap_password + "@" + nipap_host + ":" + nipap_port
    # replace with with your client name
    client_name = 'myclient'

    def __init__(self):

        # setup logging
        logging.basicConfig(format='%(asctime)s %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p',
                            filename='/tmp/NipapUtils.log', level=logging.DEBUG)
        logging.debug('Initializing connection to nipap server %s' % NipapUtils.nipap_uri)

        # a bad connection string does not result in an exception
        # check to host to do some minimal amount to verification
        try:
            response = urllib3.urlopen("http://" + NipapUtils.nipap_host + ":5000", timeout=2)
        except urllib3.URLError:
            logging.error("Cannot connect to nipap url %s" % NipapUtils.nipap_host + ":5000")
            raise pynipap.NipapAuthError

        pynipap.xmlrpc_uri = NipapUtils.nipap_uri
        a = AuthOptions({
            'authoritative_source': NipapUtils.client_name,
        })

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

    def delete_vrf(self, rt):
        """
        Deletes a vrf given the rt, does not work if the vrf has a prefix
        :param rt:
        :return: tbd
        """
        if rt is not None:
            myVRF = self.find_vrf('rt', rt)
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