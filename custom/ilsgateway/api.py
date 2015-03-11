import logging
from jsonobject import JsonObject
from jsonobject.properties import StringProperty, BooleanProperty, DecimalProperty, ListProperty, IntegerProperty,\
    FloatProperty, DictProperty
from requests.exceptions import ConnectionError
from corehq import Domain
from corehq.apps.commtrack.models import SupplyPointCase, CommtrackConfig, CommtrackActionConfig
from corehq.apps.locations.models import SQLLocation
from corehq.apps.locations.schema import LocationType
from corehq.apps.programs.models import Program
from corehq.apps.users.models import UserRole
from custom.api.utils import apply_updates
from custom.ilsgateway.models import SupplyPointStatus, DeliveryGroupReport, HistoricalLocationGroup
from custom.logistics.api import LogisticsEndpoint, APISynchronization
from corehq.apps.locations.models import Location as Loc

LOCATION_TYPES = ["MOHSW", "REGION", "DISTRICT", "FACILITY"]


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
    language = StringProperty()


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

    LOCATION_CUSTOM_FIELDS = [
        {'name': 'groups'},
    ]
    SMS_USER_CUSTOM_FIELDS = [
        {
            'name': 'role',
            'choices': [
                "district supervisor",
                "MSD",
                "imci coordinator",
                "Facility in-charge",
                "MOHSW",
                "RMO",
                "District Pharmacist",
                "DMO",
            ]
        },
        {'name': 'backend'},
    ]
    PRODUCT_CUSTOM_FIELDS = []

    def prepare_commtrack_config(self):
        """
        Bootstraps the domain-level metadata according to the static config.
        - Sets the proper location types hierarchy on the domain object.
        - Sets a keyword handler for reporting receipts
        """
        domain = Domain.get_by_name(self.domain)
        domain.location_types = []
        for i, value in enumerate(LOCATION_TYPES):
            allowed_parents = [LOCATION_TYPES[i - 1]] if i > 0 else [""]
            domain.location_types.append(
                LocationType(name=value, allowed_parents=allowed_parents,
                             administrative=(value.lower() != 'facility')))
        domain.save()
        config = CommtrackConfig.for_domain(self.domain)
        actions = [action.keyword for action in config.actions]
        if 'delivered' not in actions:
            config.actions.append(
                CommtrackActionConfig(
                    action='receipts',
                    keyword='delivered',
                    caption='Delivered')
            )
            config.save()

    def product_sync(self, ilsgateway_product):
        from custom.ilsgateway import PRODUCTS_CODES_PROGRAMS_MAPPING
        product = super(ILSGatewayAPI, self).product_sync(ilsgateway_product)
        programs = list(Program.by_domain(self.domain))
        for program, products in PRODUCTS_CODES_PROGRAMS_MAPPING.iteritems():
            if product.code in products:
                existing_program = filter(lambda p: p.name == program, programs)
                if not existing_program:
                    new_program = Program(domain=self.domain)
                    new_program.name = program
                    new_program.save()
                    product.program_id = new_program.get_id
                    product.save()
                else:
                    product.program_id = existing_program[0].get_id
                    product.save()
        return product

    def web_user_sync(self, ilsgateway_webuser):
        web_user = super(ILSGatewayAPI, self).web_user_sync(ilsgateway_webuser)
        if not web_user:
            return None
        dm = web_user.get_domain_membership(self.domain)
        dm.role_id = UserRole.get_read_only_role_by_domain(self.domain).get_id
        web_user.save()
        return web_user

    def sms_user_sync(self, ilsgateway_smsuser, **kwargs):
        from custom.logistics.commtrack import add_location
        sms_user = super(ILSGatewayAPI, self).sms_user_sync(ilsgateway_smsuser, **kwargs)
        if not sms_user:
            return None
        sp = SupplyPointCase.view('hqcase/by_domain_external_id',
                                  key=[self.domain, str(ilsgateway_smsuser.supply_point)],
                                  reduce=False,
                                  include_docs=True,
                                  limit=1).first()
        location_id = sp.location_id if sp else None
        dm = sms_user.get_domain_membership(self.domain)
        dm.location_id = location_id
        sms_user.save()
        add_location(sms_user, location_id)
        return sms_user

    def location_sync(self, ilsgateway_location, fetch_groups=False):
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
                # todo: this lookup is likely a source of slowness
                loc_parent = SupplyPointCase.view('hqcase/by_domain_external_id',
                                                  key=[self.domain, str(ilsgateway_location.parent_id)],
                                                  reduce=False,
                                                  include_docs=True).first()
                if not loc_parent:
                    parent = self.endpoint.get_location(ilsgateway_location.parent_id)
                    loc_parent = self.location_sync(Location(parent))
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
            # todo: unicode?
            location.external_id = str(ilsgateway_location.id)
            location.save()

            # todo: shouldn't this only be creating supply points for objects just at the facility level?
            # explanation: There are some sms users in ILS that are assigned to non-facility locations.
            # In HQ when we assign location to user supply point is automatically created.
            # That's reason why I'm creating supply point for all locations. Not sure how it should be solved.
            # note: I think we can now assign users to locations without making a supply point so am
            # hoping this can get changed.
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
            counter = 0
            historical_groups = {}
            while counter != 5:
                try:
                    # todo: we may be able to avoid this call by passing the groups in as part of the original
                    # location dict, though that may introduce slowness/timeouts
                    location_object = self.endpoint.get_location(
                        ilsgateway_location.id,
                        params=dict(with_historical_groups=1)
                    )
                    historical_groups = Location(**location_object).historical_groups
                    break
                except ConnectionError as e:
                    logging.error(e)
                    counter += 1

        for date, groups in historical_groups.iteritems():
            for group in groups:
                HistoricalLocationGroup.objects.get_or_create(date=date, group=group,
                                                              location_id=location.sql_location)
        return location
