from jsonobject.properties import StringProperty, BooleanProperty, ListProperty, IntegerProperty, DictProperty
from jsonobject.properties import StringProperty, BooleanProperty, ListProperty, IntegerProperty, ObjectProperty
from custom.ilsgateway.api import ProductStock, StockTransaction
from jsonobject import JsonObject
from custom.logistics.api import LogisticsEndpoint
class Group(JsonObject):
    id = IntegerProperty()
    name = StringProperty()


class SupplyPoint(JsonObject):
    id = IntegerProperty()
    active = BooleanProperty()
    code = StringProperty()
    groups = ListProperty()
    last_reported = StringProperty()
    name = StringProperty()
    primary_reporter = IntegerProperty()
    supervised_by = IntegerProperty()
    supplied_by = IntegerProperty()
    type = StringProperty()
    location_id = IntegerProperty()


class SMSUser(JsonObject):
    id = IntegerProperty()
    name = StringProperty()
    role = StringProperty()
    is_active = StringProperty()
    supply_point = ObjectProperty(item_type=SupplyPoint)
    email = StringProperty()
    phone_numbers = ListProperty()
    backend = StringProperty()
    family_name = StringProperty()
    to = StringProperty()


class EWSUser(JsonObject):
    username = StringProperty()
    first_name = StringProperty()
    last_name = StringProperty()
    email = StringProperty()
    password = StringProperty()
    is_staff = BooleanProperty()
    is_active = BooleanProperty()
    is_superuser = BooleanProperty()
    last_login = StringProperty()
    date_joined = StringProperty()
    location = IntegerProperty()
    supply_point = IntegerProperty()
    sms_notifications = BooleanProperty()
    organization = StringProperty()

    groups = ListProperty(item_type=Group)
    contact = ObjectProperty(item_type=SMSUser)


class Location(JsonObject):
    id = IntegerProperty()
    name = StringProperty()
    type = StringProperty()
    parent_id = IntegerProperty()
    latitude = StringProperty()
    longitude = StringProperty()
    code = StringProperty()
    groups = ListProperty()
    supervised_by = IntegerProperty()
    supply_points = ListProperty(item_type=SupplyPoint)
    is_active = BooleanProperty()


class Program(JsonObject):
    code = StringProperty()
    name = StringProperty()


class Product(JsonObject):
    name = StringProperty()
    units = StringProperty()
    sms_code = StringProperty()
    description = StringProperty()
    is_active = BooleanProperty()
    program = ObjectProperty(item_type=Program)


class GhanaEndpoint(LogisticsEndpoint):
    models_map = {
        'product': Product,
        'webuser': EWSUser,
        'smsuser': SMSUser,
        'location': Location,
        'product_stock': ProductStock,
        'stock_transaction': StockTransaction
    }
