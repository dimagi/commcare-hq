from jsonobject import JsonObject
from jsonobject.properties import StringProperty, BooleanProperty, DecimalProperty, ListProperty, IntegerProperty, \
    FloatProperty, DictProperty
from corehq.apps.commtrack.models import SupplyPointCase, CommtrackConfig, LocationType, CommtrackActionConfig
from corehq.apps.locations.models import SQLLocation
from corehq.apps.users.models import UserRole
from custom.api.utils import apply_updates
from custom.ilsgateway import LOCATION_TYPES, ADMINS
from custom.ilsgateway.models import SupplyPointStatus, DeliveryGroupReport, HistoricalLocationGroup
from custom.logistics.api import LogisticsEndpoint, APISynchronization
from corehq.apps.locations.models import Location as Loc


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


class ILSGatewayAPI(APISynchronization):

    def prepare_commtrack_config(self):
        config = CommtrackConfig.for_domain(self.domain)
        config.location_types = []
        for i, value in enumerate(LOCATION_TYPES):
            if not any(lt.name == value
                       for lt in config.location_types):
                allowed_parents = [LOCATION_TYPES[i - 1]] if i > 0 else [""]
                config.location_types.append(
                    LocationType(name=value, allowed_parents=allowed_parents,
                                 administrative=(value.lower() != 'facility')))
        actions = [action.keyword for action in config.actions]
        if 'delivered' not in actions:
            config.actions.append(
                CommtrackActionConfig(
                    action='receipts',
                    keyword='delivered',
                    caption='Delivered')
            )
        config.save()

    def web_users_sync(self, ilsgateway_webuser):
        web_user = super(ILSGatewayAPI, self).web_users_sync(ilsgateway_webuser)
        if not web_user:
            return None
        dm = web_user.get_domain_membership(self.domain)
        if web_user.username in ADMINS:
            dm.is_admin = True
        else:
            dm.role_id = UserRole.get_read_only_role_by_domain(self.domain).get_id
        web_user.save()

    def locations_sync(self, ilsgateway_location, fetch_groups=False):
        try:
            sql_loc = SQLLocation.objects.get(
                domain=self.domain,
                external_id=int(ilsgateway_location.id)
            )
            location = Loc.get(sql_loc.location_id)
        except SQLLocation.DoesNotExist:
            location = None
        except SQLLocation.MultipleObjectsReturned:
            return

        if not location:
            if ilsgateway_location.parent_id:
                loc_parent = SupplyPointCase.view('hqcase/by_domain_external_id',
                                                  key=[self.domain, str(ilsgateway_location.parent_id)],
                                                  reduce=False,
                                                  include_docs=True).first()
                if not loc_parent:
                    parent = self.endpoint.get_location(ilsgateway_location.parent_id)
                    loc_parent = self.locations_sync(Location(parent))
                else:
                    loc_parent = loc_parent.location
                location = Loc(parent=loc_parent)
            else:
                location = Loc()
                location.lineage = []
            location.domain = self.domain
            location.name = ilsgateway_location.name
            if ilsgateway_location.groups:
                location.metadata = {'groups': ilsgateway_location.groups}
            if ilsgateway_location.latitude:
                location.latitude = float(ilsgateway_location.latitude)
            if ilsgateway_location.longitude:
                location.longitude = float(ilsgateway_location.longitude)
            location.location_type = ilsgateway_location.type
            location.site_code = ilsgateway_location.code
            location.external_id = str(ilsgateway_location.id)
            location.save()
            if not SupplyPointCase.get_by_location(location):
                SupplyPointCase.create_from_location(self.domain, location)
        else:
            location_dict = {
                'name': ilsgateway_location.name,
                'latitude': float(ilsgateway_location.latitude) if ilsgateway_location.latitude else None,
                'longitude': float(ilsgateway_location.longitude) if ilsgateway_location.longitude else None,
                'location_type': ilsgateway_location.type,
                'site_code': ilsgateway_location.code.lower(),
                'external_id': str(ilsgateway_location.id),
                'metadata': {}
            }
            if ilsgateway_location.groups:
                location_dict['metadata']['groups'] = ilsgateway_location.groups
            case = SupplyPointCase.get_by_location(location)
            if apply_updates(location, location_dict):
                location.save()
                if case:
                    case.update_from_location(location)
                else:
                    SupplyPointCase.create_from_location(self.domain, location)
        if ilsgateway_location.historical_groups:
            historical_groups = ilsgateway_location.historical_groups
        else:
            location_object = self.endpoint.get_location(
                ilsgateway_location.id,
                params=dict(with_historical_groups=1)
            )

            historical_groups = Location(**location_object).historical_groups
        for date, groups in historical_groups.iteritems():
            for group in groups:
                HistoricalLocationGroup.objects.get_or_create(date=date, group=group,
                                                              location_id=location.sql_location)
        return location