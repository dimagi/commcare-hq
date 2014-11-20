from jsonobject.properties import StringProperty, BooleanProperty, IntegerProperty, DecimalProperty, ListProperty
from custom.ilsgateway.api import ILSGatewayEndpoint, Product, ProductStock, StockTransaction
from jsonobject import JsonObject

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
    location = DecimalProperty()
    supply_point = DecimalProperty()
    sms_notifications = BooleanProperty()
    organization = StringProperty()

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
            supply_point=json_rep['supply_point'],
            sms_notifications=json_rep['sms_notifications'],
            organization=json_rep['organization'],
        )

    def __repr__(self):
        return str(self.__dict__)


class SMSUser(JsonObject):
    id = DecimalProperty()
    name = StringProperty()
    role = StringProperty()
    is_active = StringProperty()
    supply_point = DecimalProperty()
    email = StringProperty()
    phone_numbers = ListProperty()
    backend = StringProperty()
    family_name = StringProperty()
    to = StringProperty()

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
            backend=json_rep['backend'],
            family_name=json_rep['family_name'],
            to=json_rep['to']
        )

    def __repr__(self):
        return str(self.__dict__)


class Location(JsonObject):
    id = DecimalProperty()
    name = StringProperty()
    location_type = StringProperty()
    parent = DecimalProperty()
    latitude = StringProperty()
    longitude = StringProperty()
    code = StringProperty()
    groups = ListProperty()
    historical_groups = ListProperty()
    created_at = StringProperty()
    supervised_by = DecimalProperty()

    @classmethod
    def from_json(cls, json_rep):
        return cls(
            id=json_rep['id'],
            name=json_rep['name'],
            location_type=json_rep['type'],
            parent=json_rep['parent_id'],
            latitude=json_rep['latitude'],
            longitude=json_rep['longitude'],
            code=json_rep['code'],
            groups=json_rep['groups'],
            created_at=json_rep['created_at'],
            supervised_by=json_rep['supervised_by']
        )

    def __repr__(self):
        return str(self.__dict__)


class GhanaEndpoint(ILSGatewayEndpoint):
    models_map = {
        'product': Product,
        'webuser': EWSUser,
        'smsuser': SMSUser,
        'location': Location,
        'product_stock': ProductStock,
        'stock_transaction': StockTransaction
    }