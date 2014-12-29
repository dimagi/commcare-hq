from jsonobject import JsonObject
from jsonobject.properties import StringProperty, BooleanProperty, DecimalProperty, ListProperty, IntegerProperty, \
    FloatProperty, DictProperty
from corehq.apps.commtrack.models import SupplyPointCase
from custom.ilsgateway.models import SupplyPointStatus, DeliveryGroupReport
from custom.logistics.api import LogisticsEndpoint


class Product(JsonObject):
    name = StringProperty()
    units = StringProperty()
    sms_code = StringProperty()
    description = StringProperty()
    is_active = BooleanProperty()


class ILSUser(JsonObject):
    username = StringProperty()
    first_name = StringProperty()
    last_name = StringProperty()
    email = StringProperty()
    password = StringProperty()
    is_staff = BooleanProperty(default=False)
    is_active = BooleanProperty()
    is_superuser = BooleanProperty(default=False)
    last_login = StringProperty()
    date_joined = StringProperty()
    location = DecimalProperty()
    supply_point = IntegerProperty()

    @classmethod
    def from_json(cls, json_rep):
        return cls(
            username=json_rep['username'],
            first_name=json_rep['first_name'],
            last_name=json_rep['last_name'],
            email=json_rep['email'],
            password=json_rep['password'],
            is_staff=json_rep['is_staff'],
            is_active=json_rep['is_active'],
            is_superuser=json_rep['is_superuser'],
            last_login=json_rep['last_login'],
            date_joined=json_rep['date_joined'],
            location=json_rep['location'],
            supply_point=json_rep['supply_point']
        )


class SMSUser(JsonObject):
    id = IntegerProperty()
    name = StringProperty()
    role = StringProperty()
    is_active = StringProperty()
    supply_point = DecimalProperty()
    email = StringProperty()
    phone_numbers = ListProperty()
    backend = StringProperty()
    date_updated = StringProperty()

    @classmethod
    def from_json(cls, json_rep):
        return cls(
            id=json_rep['id'],
            name=json_rep['name'],
            role=json_rep['role'],
            is_active=json_rep['is_active'],
            supply_point=json_rep['supply_point'],
            email=json_rep['email'],
            phone_numbers=json_rep['phone_numbers'],
            backend=json_rep['backend']
        )


class Location(JsonObject):
    id = IntegerProperty()
    name = StringProperty()
    type = StringProperty()
    parent_id = IntegerProperty()
    latitude = StringProperty()
    longitude = StringProperty()
    code = StringProperty()
    groups = ListProperty()
    historical_groups = DictProperty()


class ProductStock(JsonObject):
    supply_point = IntegerProperty()
    quantity = FloatProperty()
    product = StringProperty()
    last_modified = StringProperty()
    auto_monthly_consumption = FloatProperty()


class StockTransaction(JsonObject):
    beginning_balance = DecimalProperty()
    date = StringProperty()
    ending_balance = DecimalProperty()
    product = StringProperty()
    quantity = DecimalProperty()
    report_type = StringProperty()
    supply_point = IntegerProperty()


def _get_location_id(facility, domain):
        sp = SupplyPointCase.view('hqcase/by_domain_external_id',
                                  key=[domain, str(facility)],
                                  reduce=False,
                                  include_docs=True).first()
        return sp.location_id


class ILSGatewayEndpoint(LogisticsEndpoint):

    models_map = {
        'product': Product,
        'webuser': ILSUser,
        'smsuser': SMSUser,
        'location': Location,
        'product_stock': ProductStock,
        'stock_transaction': StockTransaction
    }

    def __init__(self, base_uri, username, password):
        super(ILSGatewayEndpoint, self).__init__(base_uri, username, password)
        self.supplypointstatuses_url = self._urlcombine(self.base_uri, '/supplypointstatus/')
        self.deliverygroupreports_url = self._urlcombine(self.base_uri, '/deliverygroupreports/')

    def get_supplypointstatuses(self, domain, facility, **kwargs):
        meta, supplypointstatuses = self.get_objects(self.supplypointstatuses_url, **kwargs)
        location_id = _get_location_id(facility, domain)
        return meta, [SupplyPointStatus.wrap_from_json(supplypointstatus, location_id) for supplypointstatus in
                      supplypointstatuses]

    def get_deliverygroupreports(self, domain, facility, **kwargs):
        meta, deliverygroupreports = self.get_objects(self.deliverygroupreports_url, **kwargs)
        location_id = _get_location_id(facility, domain)
        return meta, [DeliveryGroupReport.wrap_from_json(deliverygroupreport, location_id)
                      for deliverygroupreport in deliverygroupreports]
