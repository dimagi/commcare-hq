from custom.ilsgateway.api import ILSGatewayEndpoint, Product, ProductStock, StockTransaction


class EWSUser(object):
    def __init__(self, username, first_name, last_name, email,
                 password, is_staff, is_active, is_superuser, last_login,
                 date_joined, location, supply_point, sms_notifications, organization):
        self.username = username
        self.first_name = first_name
        self.last_name = last_name
        self.email = email
        self.password = password
        self.is_staff = is_staff
        self.is_active = is_active
        self.is_superuser = is_superuser
        self.last_login = last_login
        self.date_joined = date_joined
        self.location = location
        self.supply_point = supply_point
        self.sms_notifications = sms_notifications
        self.organization = organization

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


class SMSUser(object):
    def __init__(self, id, name, role, is_active, supply_point, email, phone_numbers, backend, family_name, to):
        self.id = id
        self.name = name
        self.role = role
        self.is_active = is_active
        self.supply_point = supply_point
        self.email = email
        self.phone_numbers = phone_numbers
        self.backend = backend
        self.family_name = family_name
        self.to = to

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



class Location(object):
    def __init__(self, id, name, location_type, parent, latitude, longitude, code, groups, created_at, supervised_by):
        self.id = id
        self.name = name
        self.location_type = location_type
        self.parent = parent
        self.latitude = latitude
        self.longitude = longitude
        self.code = code
        self.groups = groups
        self.created_at = created_at
        self.supervised_by = supervised_by

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