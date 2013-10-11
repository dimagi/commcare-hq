from custom.openlmis.api import OpenLMISEndpoint


class MockOpenLMISEndpoint(OpenLMISEndpoint):

    def create_virtual_facility(self, facility_data):
        return True

