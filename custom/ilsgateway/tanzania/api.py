from custom.ilsgateway.api import ILSGatewayEndpoint
from custom.ilsgateway.models import SupplyPointStatus, DeliveryGroupReport


class TanzaniaEndpoint(ILSGatewayEndpoint):
    def __init__(self, base_uri, username, password):
        super(TanzaniaEndpoint, self).__init__(base_uri, username, password)
        self.supplypointstatuses_url = self._urlcombine(self.base_uri, '/supplypointstatus/')
        self.deliverygroupreports_url = self._urlcombine(self.base_uri, '/deliverygroupreports/')

    def get_supplypointstatuses(self, domain, facility, **kwargs):
        meta, supplypointstatuses = self.get_objects(self.supplypointstatuses_url, **kwargs)
        location_id = self._get_location_id(facility, domain)
        return meta, [SupplyPointStatus.wrap_from_json(supplypointstatus, location_id) for supplypointstatus in
                      supplypointstatuses]

    def get_deliverygroupreports(self, domain, facility, **kwargs):
        meta, deliverygroupreports = self.get_objects(self.deliverygroupreports_url, **kwargs)
        location_id = self._get_location_id(facility, domain)
        return meta, [DeliveryGroupReport.wrap_from_json(deliverygroupreport, location_id)
                      for deliverygroupreport in deliverygroupreports]