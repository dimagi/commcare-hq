from custom.openlmis.api import OpenLMISEndpoint


class MockOpenLMISEndpoint(OpenLMISEndpoint):

    def create_virtual_facility(self, facility_data):
        return True

    def update_virtual_facility(self, id, facility_data):
        return True

    def submit_requisition(self, requisition_data):
        return True
