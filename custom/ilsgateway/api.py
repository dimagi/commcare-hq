from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from corehq.apps.hqcase.dbaccessors import \
    get_supply_point_case_in_domain_by_id
from corehq.apps.locations.util import get_lineage_from_location_id
from corehq.apps.sms.mixin import PhoneNumberInUseException, InvalidFormatException, apply_leniency, VerifiedNumber
from corehq.form_processor.interfaces.supply import SupplyInterface
from dimagi.ext.jsonobject import JsonObject, StringProperty, BooleanProperty, DecimalProperty, ListProperty, IntegerProperty,\
    FloatProperty, DictProperty
from corehq.apps.commtrack.models import CommtrackConfig, CommtrackActionConfig
from corehq.apps.locations.models import SQLLocation, LocationType
from corehq.apps.programs.models import Program
from corehq.apps.users.models import UserRole, WebUser
from custom.api.utils import apply_updates
from custom.ilsgateway.models import SupplyPointStatus, DeliveryGroupReport, HistoricalLocationGroup, \
    ILSGatewayWebUser, ILSGatewayConfig, location_edited_receiver
from custom.logistics.api import LogisticsEndpoint, APISynchronization, ApiSyncObject
from corehq.apps.locations.models import Location as Loc

LOCATION_TYPES = ["MOHSW", "MSDZONE", "REGION", "DISTRICT", "FACILITY"]
MSDZONE_MAP = {
    'Dar Es Salaam Zone': ['DR', 'morogoro', 'coast', 'dar es salaam', 'pwani'],
    'Dodoma Zone': ['DM', 'singida', 'dodoma'],
    'Iringa Zone': ['IR', 'njombe', 'iringa'],
    'Mbeya Zone': ['MB', 'rukwa', 'mbeya', 'mbeya', 'katavi'],
    'Moshi Zone': ['MS', 'arusha', 'manyara', 'kilimanjaro'],
    'Mtwara Zone': ['MT', 'ruvuma', 'lindi', 'mtwara'],
    'Mwanza Zone': ['MZ', 'geita', 'shinyanga', 'simiyu', 'mwanza', 'kagera', 'mara'],
    'Tabora Zone': ['TB', 'kigoma', 'tabora'],
    'Tanga Zone': ['TG', 'tanga'],
    'Zanzibar Zone': ['D', "pemba north", "pemba south", "zanzibar central/south", "zanzibar north",
                      "zanzibar west"],
    'UNKNOWN': ['UN']
}


class Product(JsonObject):
    name = StringProperty()
    units = StringProperty()
    sms_code = StringProperty()
    description = StringProperty()
    is_active = BooleanProperty()


class ILSUser(JsonObject):
    id = IntegerProperty()
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


class Connection(JsonObject):
    phone_number = StringProperty()
    backend = StringProperty()
    default = BooleanProperty()


class SMSUser(JsonObject):
    id = IntegerProperty()
    name = StringProperty()
    role = StringProperty()
    is_active = StringProperty()
    supply_point = DecimalProperty()
    email = StringProperty()
    phone_numbers = ListProperty(item_type=Connection)
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


class Groups(JsonObject):
    location_id = IntegerProperty()
    groups = DictProperty()


def _get_location_id(facility, domain):
    supply_point = get_supply_point_case_in_domain_by_id(domain, facility)
    return supply_point.location_id if supply_point else None


def _get_msd_name(loc):
    for k, v in MSDZONE_MAP.iteritems():
        if loc.lower() in v:
            return k
    return 'UNKNOWN'


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
        self.groups = self._urlcombine(self.base_uri, '/groups/')

    def get_supplypointstatuses(self, domain, facility=None, **kwargs):
        meta, supplypointstatuses = self.get_objects(self.supplypointstatuses_url, **kwargs)
        location = None
        if facility:
            try:
                location = SQLLocation.objects.get(domain=domain, external_id=facility)
            except SQLLocation.DoesNotExist:
                return meta, []

        statuses = []
        for supplypointstatus in supplypointstatuses:
            if not location:
                try:
                    statuses.append(SupplyPointStatus.wrap_from_json(supplypointstatus, SQLLocation.objects.get(
                        domain=domain,
                        external_id=supplypointstatus['supply_point']
                    )))
                except SQLLocation.DoesNotExist:
                    continue
            else:
                statuses.append(SupplyPointStatus.wrap_from_json(supplypointstatus, location))
        return meta, statuses

    def get_deliverygroupreports(self, domain, facility=None, **kwargs):
        meta, deliverygroupreports = self.get_objects(self.deliverygroupreports_url, **kwargs)
        location = None
        if facility:
            try:
                location = SQLLocation.objects.get(domain=domain, external_id=facility)
            except SQLLocation.DoesNotExist:
                return meta, []

        reports = []
        for deliverygroupreport in deliverygroupreports:
            if not location:
                try:
                    reports.append(DeliveryGroupReport.wrap_from_json(deliverygroupreport, SQLLocation.objects.get(
                        domain=domain,
                        external_id=deliverygroupreport['supply_point']
                    )))
                except SQLLocation.DoesNotExist:
                    continue
            else:
                reports.append(DeliveryGroupReport.wrap_from_json(deliverygroupreport, location))

        return meta, reports

    def get_groups(self, **kwargs):
        meta, groups_list = self.get_objects(self.groups, **kwargs)
        return meta, [
            Groups(obj) for obj in groups_list
        ]

    def get_stocktransactions(self, filters=None, **kwargs):
        filters = filters or {}
        meta, stock_transactions = self.get_objects(self.stocktransactions_url, filters=filters, **kwargs)
        return meta, [(self.models_map['stock_transaction'])(stock_transaction)
                      for stock_transaction in stock_transactions]


EXCLUDED_REGIONS = [
    24, 25, 26, 27, 148
]


class ILSGatewayAPI(APISynchronization):

    LOCATION_CUSTOM_FIELDS = [
        {
            'name': 'group',
            'choices': ['A', 'B', 'C']
        },
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

    @property
    def apis(self):
        return [
            ApiSyncObject('product', self.endpoint.get_products, self.product_sync),
            ApiSyncObject(
                'location_region',
                self.endpoint.get_locations,
                self.location_sync,
                'date_updated',
                filters={
                    'type': 'region',
                    'is_active': True
                }
            ),
            ApiSyncObject(
                'location_district',
                self.endpoint.get_locations,
                self.location_sync,
                'date_updated',
                filters={
                    'type': 'district',
                    'is_active': True
                }
            ),
            ApiSyncObject(
                'location_facility',
                self.endpoint.get_locations,
                self.location_sync,
                'date_updated',
                filters={
                    'type': 'facility',
                    'is_active': True
                }
            ),
            ApiSyncObject(
                'location_groups',
                self.endpoint.get_groups,
                self.location_groups_sync,
                migrate_once=True
            ),
            ApiSyncObject('webuser', self.endpoint.get_webusers, self.web_user_sync, 'date_updated'),
            ApiSyncObject('smsuser', self.endpoint.get_smsusers, self.sms_user_sync, 'date_updated')
        ]

    def create_or_edit_roles(self):
        pass

    def prepare_commtrack_config(self):
        """
        Bootstraps the domain-level metadata according to the static config.
        - Sets the proper location types hierarchy on the domain object.
        - Sets a keyword handler for reporting receipts
        """
        for location_type in LocationType.objects.by_domain(self.domain):
            location_type.delete()

        previous = None
        for loc_type in LOCATION_TYPES:
            previous, _ = LocationType.objects.get_or_create(
                domain=self.domain,
                name=loc_type,
                parent_type=previous,
                administrative=(loc_type != 'FACILITY'),
            )

        config = CommtrackConfig.for_domain(self.domain)
        config.consumption_config.exclude_invalid_periods = True
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

    def _create_web_user(self, email, ilsgateway_webuser, location_id, user_dict):
        user = WebUser.create(domain=None, username=email,
                              password=ilsgateway_webuser.password, email=ilsgateway_webuser.email.lower(),
                              **user_dict)
        user.add_domain_membership(self.domain, location_id=location_id)
        dm = user.get_domain_membership(self.domain)
        dm.role_id = UserRole.get_read_only_role_by_domain(self.domain).get_id
        user.save()
        return user

    def _edit_web_user(self, user, location_id):
        read_only_role = UserRole.get_read_only_role_by_domain(self.domain).get_id
        if self.domain not in user.get_domains():
            user.add_domain_membership(self.domain, location_id=location_id, role_id=read_only_role)
            user.save()
        else:
            dm = user.get_domain_membership(self.domain)
            if dm.role_id != read_only_role or dm.location_id != location_id:
                dm.role_id = read_only_role
                dm.location_id = location_id
                user.save()

    def web_user_sync(self, ilsgateway_webuser):
        email = ilsgateway_webuser.email.lower()
        if not email:
            try:
                validate_email(ilsgateway_webuser.username)
                email = ilsgateway_webuser.username
            except ValidationError:
                return None
        user = WebUser.get_by_username(email)
        user_dict = {
            'first_name': ilsgateway_webuser.first_name,
            'last_name': ilsgateway_webuser.last_name,
            'is_active': ilsgateway_webuser.is_active,
            'password_hashed': True,
        }
        location_id = None
        if ilsgateway_webuser.location:
            try:
                sql_location = SQLLocation.objects.get(domain=self.domain, external_id=ilsgateway_webuser.location)
                location_id = sql_location.location_id
            except SQLLocation.DoesNotExist:
                location_id = None

        if user is None:
            try:
                ils_sql_web_user = ILSGatewayWebUser.objects.get(external_id=ilsgateway_webuser.id)
            except ILSGatewayWebUser.DoesNotExist:
                ils_sql_web_user = None

            if ils_sql_web_user:
                # if user exists in db it means he was already migrated but he changed email in v1
                old_email = ils_sql_web_user.email
                user = WebUser.get_by_username(old_email)
                if user:
                    user.delete_domain_membership(self.domain)
                    user.save()
                user = self._create_web_user(email, ilsgateway_webuser, location_id, user_dict)
                ils_sql_web_user.email = email
                ils_sql_web_user.save()
                return user

            else:
                user = self._create_web_user(email, ilsgateway_webuser, location_id, user_dict)
        else:
            self._edit_web_user(user, location_id)

        ilsgateway_webuser, _ = ILSGatewayWebUser.objects.get_or_create(
            external_id=ilsgateway_webuser.id,
        )
        ilsgateway_webuser.email = email
        ilsgateway_webuser.save()
        return user

    def _reassign_number(self, user, connection):
        v = VerifiedNumber.by_phone(apply_leniency(connection.phone_number), include_pending=True)
        if v.domain in self._get_logistics_domains():
            v.domain = self.domain
            v.owner_doc_type = user.doc_type
            v.owner_id = user.get_id
            backend_id = None
            if connection.backend != 'push_backend':
                backend_id = 'MOBILE_BACKEND_TEST'
            v.backend_id = backend_id
            v.verified = True
            v.save()

    def _save_verified_number(self, user, connection):
        try:
            self.save_verified_number(user, connection)
        except PhoneNumberInUseException:
            self._reassign_number(user, connection)
        except InvalidFormatException:
            pass

    def save_verified_number(self, user, connection):
        backend_id = None
        if connection.backend != 'push_backend':
            backend_id = 'MOBILE_BACKEND_TEST'
        user.save_verified_number(self.domain, connection.phone_number, True, backend_id=backend_id)

    def add_phone_numbers(self, ilsgateway_smsuser, user):
        phone_numbers = ilsgateway_smsuser.phone_numbers
        if not phone_numbers:
            return

        saved_numbers = []
        for connection in phone_numbers:
            phone_number = apply_leniency(connection.phone_number)
            if connection.default:
                saved_numbers = [phone_number] + saved_numbers
            else:
                saved_numbers.append(phone_number)
        user.phone_numbers = saved_numbers
        user.save()

        for connection in phone_numbers:
            self._save_verified_number(user, connection)

    def edit_phone_numbers(self, ilsgateway_smsuser, user):
        phone_numbers = set(user.phone_numbers)
        saved_numbers = []

        for connection in ilsgateway_smsuser.phone_numbers:
            phone_number = apply_leniency(connection.phone_number)
            if phone_number not in phone_numbers:
                self._save_verified_number(user, connection)
            if connection.default:
                saved_numbers = [phone_number] + saved_numbers
            else:
                saved_numbers.append(phone_number)

        for phone_number in phone_numbers - set(saved_numbers):
            user.delete_verified_number(phone_number)

        user.phone_numbers = saved_numbers
        user.save()

    def sms_user_sync(self, ilsgateway_smsuser, **kwargs):
        sms_user = super(ILSGatewayAPI, self).sms_user_sync(ilsgateway_smsuser, **kwargs)
        if not sms_user:
            return None

        sms_user.save()
        if ilsgateway_smsuser.supply_point:
            try:
                location = SQLLocation.objects.get(domain=self.domain, external_id=ilsgateway_smsuser.supply_point)
                sms_user.set_location(location.couch_location)
            except SQLLocation.DoesNotExist:
                pass
        return sms_user

    def location_sync(self, ilsgateway_location):
        def get_or_create_msd_zone(region):
            msd_name = _get_msd_name(region.name)
            msd_code = MSDZONE_MAP[msd_name][0]
            try:
                sql_msd_loc = SQLLocation.objects.get(
                    domain=self.domain,
                    site_code=msd_code
                )
                msd_location = Loc.get(sql_msd_loc.location_id)
            except SQLLocation.DoesNotExist:
                msd_location = Loc(parent=loc_parent)

            msd_location.domain = self.domain
            msd_location.name = msd_name
            msd_location.location_type = 'MSDZONE'
            msd_location.site_code = MSDZONE_MAP[msd_name][0]
            msd_location.save()
            return msd_location

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
            if ilsgateway_location.id in EXCLUDED_REGIONS:
                return

            if ilsgateway_location.parent_id:
                try:
                    sql_loc_parent = SQLLocation.objects.get(
                        domain=self.domain,
                        external_id=ilsgateway_location.parent_id
                    )
                    loc_parent = sql_loc_parent.couch_location
                except SQLLocation.DoesNotExist:
                    new_parent = self.endpoint.get_location(ilsgateway_location.parent_id)
                    loc_parent = self.location_sync(Location(new_parent))
                    if not loc_parent:
                        return

                if ilsgateway_location.type == 'REGION':
                    location = Loc(parent=get_or_create_msd_zone(ilsgateway_location))
                else:
                    location = Loc(parent=loc_parent)
            else:
                location = Loc()
                location.lineage = []
            location.domain = self.domain
            location.name = ilsgateway_location.name
            if ilsgateway_location.groups:
                location.metadata = {'group': ilsgateway_location.groups[0]}
            if ilsgateway_location.latitude:
                location.latitude = float(ilsgateway_location.latitude)
            if ilsgateway_location.longitude:
                location.longitude = float(ilsgateway_location.longitude)
            location.location_type = ilsgateway_location.type
            location.site_code = ilsgateway_location.code
            location.external_id = unicode(ilsgateway_location.id)
            location.save()

            interface = SupplyInterface(self.domain)
            if ilsgateway_location.type == 'FACILITY':
                if not interface.get_by_location(location):
                    interface.create_from_location(self.domain, location)
                    location.save()
                else:
                    sql_location = location.sql_location
                    if not sql_location.supply_point_id:
                        location.save()
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
                location_dict['metadata']['group'] = ilsgateway_location.groups[0]
            case = SupplyInterface(self.domain).get_by_location(location)
            if apply_updates(location, location_dict):
                location.save()
                if case:
                    case.update_from_location(location)
                else:
                    SupplyInterface.create_from_location(self.domain, location)
            location_parent = location.parent
            if ilsgateway_location.type == 'FACILITY' and ilsgateway_location.parent_id and location_parent \
                    and location_parent.external_id != str(ilsgateway_location.parent_id):
                new_parent = self.endpoint.get_location(ilsgateway_location.parent_id)
                new_parent = self.location_sync(Location(new_parent))
                location.lineage = get_lineage_from_location_id(new_parent.get_id)
                location.save()
                location.previous_parents = [location_parent.get_id]
                location_edited_receiver(None, location, moved=True)
        return location

    def location_groups_sync(self, location_groups):
        with transaction.atomic():
            for date, groups in location_groups.groups.iteritems():
                try:
                    sql_location = SQLLocation.objects.get(
                        external_id=location_groups.location_id,
                        domain=self.domain
                    )
                except SQLLocation.DoesNotExist:
                    continue
                for group in groups:
                    HistoricalLocationGroup.objects.get_or_create(date=date, group=group,
                                                                  location_id=sql_location)
