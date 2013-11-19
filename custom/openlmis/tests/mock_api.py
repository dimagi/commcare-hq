import json
import os
from custom.openlmis.api import OpenLMISEndpoint, RequisitionDetails


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

    def get_requisition_details(self, requisition_id):
        with open(os.path.join(self.datapath, 'sample_requisition_details.json')) as f:
            requisition = RequisitionDetails.from_json(json.loads(f.read()))
        return requisition