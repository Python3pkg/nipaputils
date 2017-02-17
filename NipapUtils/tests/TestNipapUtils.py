import nose.tools
import unittest
from NipapUtils import NipapUtils


class TestNipapUtils(object):
    handle = None
    VRF_NAME = "TDD VRF"
    RT = "123:7654"
    DESCRIPTION="UNIT TEST"
    SITE = 'DEV'  # not used at this time, could match on VRF property such as name or description
    PREFIX24 = "10.173.129.0/24"
    TAGS = ["tag1", "tag2"]

    @classmethod
    def setup_class(cls):
        TestNipapUtils.handle = NipapUtils()

    def test_02(self):
        '''
        Test adding a VRF
        :return:
        '''
        vrf = TestNipapUtils.handle.add_vrf(self.VRF_NAME, self.RT, self.DESCRIPTION)
        nose.tools.assert_is_not_none(vrf, "Expected a VRF to be created")

    def test_03(self):
        '''
        Test finding a VRF
        :return:
        '''
        result = TestNipapUtils.handle.find_vrf("name", self.VRF_NAME)
        nose.tools.assert_is_not_none(result, "Expected a VRF to be found")

    def test_04(self):
        '''
        Negative test, try and find a non-existant VRF
        :return:
        '''
        result = TestNipapUtils.handle.find_vrf("name", "NOT FOUND VRF")
        nose.tools.assert_is_none(result, "Expected VRF not to be found")

    def test_06(self):
        '''
        Test reserving a /24 address under a VRF
        :return:
        '''
        type = "reservation"
        status = "reserved"

        retVal = TestNipapUtils.handle.get_ipam_ip_24(self.SITE, self.RT, self.PREFIX24,
                                                      type, status, self.DESCRIPTION, self.TAGS)
        nose.tools.assert_is_not_none(retVal, "expected to reserve a 24")

    def test_07(self):
        '''
        Test reserving a /24 address under a VRF, if reserved just returns the existing
        :return:
        '''
        type = "reservation"
        status = "reserved"

        # NOTE, if the network already exists, returns existing...
        retVal = TestNipapUtils.handle.get_ipam_ip_24(self.SITE, self.RT, self.PREFIX24,
                                                      type, status, self.DESCRIPTION, self.TAGS)
        nose.tools.assert_is_not_none(retVal, "expected to reserve a 24")

    def test_08(self):
        '''
        Test finding a prefix
        :return:
        '''
        myPrefix = TestNipapUtils.handle.find_prefix(self.RT, self.PREFIX24)
        nose.tools.assert_equal(self.PREFIX24, myPrefix.prefix, "Expected to find prefix")

    def test_09(self):
        result = TestNipapUtils.handle.delete_vrf(self.RT)
        nose.tools.assert_is_not_none(result, "Expected a VRF to be deleted")


    def test_10(self):
        '''
        Test inserting a vlan into postgress, underlying NIPAP
        :return:
        '''

        result = TestNipapUtils.handle.insertVlan(vlanid=1234, siteid="SJP", cug="CUG-123",
                                                  enterprisename="Test Enterprise", porttype="DC")
        nose.tools.assert_is_not_none(result, "Expected to insert vlan")


    def test_11(self):
        '''
        Test query of the VLAN
        :return:
        '''

        result = TestNipapUtils.handle.queryVlanByIdPort(vlanid=1234, porttype='DC')
        nose.tools.assert_is_not_none(result, "Expected to find a vlan")

    def test_12(self):
        '''
        Test the deletion of a vlan
        :return:
        '''

        result = TestNipapUtils.handle.deleteVlan(vlanid=1234, porttype='DC')