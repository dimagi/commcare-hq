from custom.openlmis.api import OpenLMISEndpoint


class MockOpenLMISEndpoint(OpenLMISEndpoint):

    def create_virtual_facility(self, facility_data):
        return True

    def update_virtual_facility(self, id, facility_data):
        return True

    def submit_requisition(self, requisition_data):
        return True

    def approve_requisition(self, requisition_data):
        return True

    def confirm_delivery(self, order_id, delivery_date):
        return True


class MockOpenLMISSubmitEndpoint(OpenLMISEndpoint):
    def submit_requisition(self, requisition_data):
        return {'requisitionId': 'REQ_123'}