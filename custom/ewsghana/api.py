from jsonobject.properties import StringProperty, BooleanProperty, ListProperty, IntegerProperty, DictProperty
from custom.ilsgateway.api import ProductStock, StockTransaction
from jsonobject import JsonObject
from custom.logistics.api import LogisticsEndpoint


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


class SMSUser(JsonObject):
    id = IntegerProperty()
    name = StringProperty()
    role = StringProperty()
    is_active = StringProperty()
    supply_point = IntegerProperty()
    email = StringProperty()
    phone_numbers = ListProperty()
    backend = StringProperty()
    family_name = StringProperty()
    to = StringProperty()


class Location(JsonObject):
    id = IntegerProperty()
    name = StringProperty()
    type = StringProperty()
    parent_id = IntegerProperty()
    latitude = StringProperty()
    longitude = StringProperty()
    code = StringProperty()
    groups = ListProperty()
    historical_groups = ListProperty()
    created_at = StringProperty()
    supervised_by = IntegerProperty()
    is_active = BooleanProperty()


class Program(JsonObject):
    code = IntegerProperty()
    name = StringProperty()


class Product(JsonObject):
    name = StringProperty()
    units = StringProperty()
    sms_code = StringProperty()
    description = StringProperty()
    is_active = BooleanProperty()
    program = DictProperty()


class GhanaEndpoint(LogisticsEndpoint):
    models_map = {
        'product': Product,
        'webuser': EWSUser,
        'smsuser': SMSUser,
        'location': Location,
        'product_stock': ProductStock,
        'stock_transaction': StockTransaction
    }
