import logging
from django.core.validators import validate_email
import requests
from corehq.apps.commtrack.dbaccessors.supply_point_case_by_domain_external_id import \
    get_supply_point_case_by_domain_external_id
from corehq.apps.products.models import SQLProduct
from custom.ewsghana.models import FacilityInCharge
from custom.ewsghana.utils import TEACHING_HOSPITAL_MAPPING, TEACHING_HOSPITALS
from dimagi.utils.dates import force_to_datetime
from corehq.apps.commtrack.models import SupplyPointCase, CommtrackConfig
from corehq.apps.locations.models import SQLLocation, LocationType
from corehq.apps.users.models import WebUser, UserRole, Permissions
from custom.api.utils import apply_updates
from custom.ewsghana.extensions import ews_product_extension, ews_webuser_extension
from dimagi.ext.jsonobject import JsonObject, StringProperty, BooleanProperty, ListProperty, \
    IntegerProperty, ObjectProperty
from custom.logistics.api import LogisticsEndpoint, APISynchronization, MigrationException, ApiSyncObject
from corehq.apps.locations.models import Location as Loc
from django.core.exceptions import ValidationError


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
    products = ListProperty()
    incharges = ListProperty()


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
    language = StringProperty()


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
    contact = ObjectProperty(item_type=SMSUser, default=None)


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
    from custom.ilsgateway.api import ProductStock, StockTransaction
    models_map = {
        'product': Product,
        'webuser': EWSUser,
        'smsuser': SMSUser,
        'location': Location,
        'product_stock': ProductStock,
        'stock_transaction': StockTransaction
    }

    def __init__(self, base_uri, username, password):
        super(GhanaEndpoint, self).__init__(base_uri, username, password)
        self.supply_point_url = self._urlcombine(self.base_uri, '/supplypoints/')

    def get_supply_points(self, **kwargs):
        meta, supply_points = self.get_objects(self.supply_point_url, **kwargs)
        return meta, [SupplyPoint(supply_point) for supply_point in supply_points]

    def get_stocktransactions(self, **kwargs):
        meta, stock_transactions = self.get_objects(self.stocktransactions_url, **kwargs)
        return meta, [(self.models_map['stock_transaction'])(stock_transaction)
                      for stock_transaction in stock_transactions]

    def get_smsuser(self, user_id, **kwargs):
        response = requests.get(self.smsusers_url + str(user_id) + "/", auth=self._auth())
        return SMSUser(response.json())


class EWSApi(APISynchronization):
    LOCATION_CUSTOM_FIELDS = [
        {'name': 'created_at'},
        {'name': 'supervised_by'}
    ]
    SMS_USER_CUSTOM_FIELDS = [
        {'name': 'to'},
        {'name': 'backend'},
        {
            'name': 'role',
            'choices': [
                'In Charge', 'Nurse', 'Pharmacist', 'Laboratory Staff', 'Other', 'Facility Manager'
            ],
            'label': 'roles',
            'is_multiple_choice': True
        }
    ]
    PRODUCT_CUSTOM_FIELDS = []

    @property
    def apis(self):
        return [
            ApiSyncObject('product', self.endpoint.get_products, self.product_sync),
            ApiSyncObject(
                'location_country',
                self.endpoint.get_locations,
                self.location_sync,
                'date_updated',
                filters={
                    'type': 'country',
                    'is_active': True
                }
            ),
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
            ApiSyncObject('webuser', self.endpoint.get_webusers, self.web_user_sync, 'user__date_joined'),
            ApiSyncObject('smsuser', self.endpoint.get_smsusers, self.sms_user_sync, 'date_updated')
        ]

    def _create_location_from_supply_point(self, supply_point, location):
        try:
            sql_location = SQLLocation.objects.get(domain=self.domain, site_code=supply_point.code)
            return Loc.get(sql_location.location_id)
        except SQLLocation.DoesNotExist:
            parent = location
            if supply_point.code in TEACHING_HOSPITAL_MAPPING:
                parent = self._sync_parent(TEACHING_HOSPITAL_MAPPING[supply_point.code]['parent_external_id'])

            new_location = Loc(parent=parent)
            new_location.domain = self.domain
            new_location.location_type = supply_point.type
            new_location.name = supply_point.name
            new_location.site_code = supply_point.code
            if supply_point.supervised_by:
                new_location.metadata['supervised_by'] = supply_point.supervised_by
            new_location.save()
            sql_loc = new_location.sql_location
            sql_loc.products = SQLProduct.objects.filter(domain=self.domain, code__in=supply_point.products)
            sql_loc.save()
            return new_location

    def _create_supply_point_from_location(self, supply_point, location):
        if not SupplyPointCase.get_by_location(location):
            if supply_point.supervised_by:
                location.metadata['supervised_by'] = supply_point.supervised_by
                location.save()
                sql_loc = location.sql_location
                sql_loc.products = SQLProduct.objects.filter(domain=self.domain, code__in=supply_point.products)
                sql_loc.save()
            return SupplyPointCase.get_or_create_by_location(Loc(_id=location._id,
                                                             name=supply_point.name,
                                                             external_id=str(supply_point.id),
                                                             domain=self.domain))

    def _make_loc_type(self, name, administrative=False, parent_type=None):
        return LocationType.objects.get_or_create(
            domain=self.domain,
            name=name,
            administrative=administrative,
            parent_type=parent_type,
        )[0]

    def prepare_commtrack_config(self):
        for location_type in LocationType.objects.by_domain(self.domain):
            location_type.delete()

        country = self._make_loc_type(name="country", administrative=True)
        self._make_loc_type(name="Central Medical Store", parent_type=country)

        region = self._make_loc_type(name="region", administrative=True,
                                     parent_type=country)
        self._make_loc_type(name="Teaching Hospital", parent_type=region)
        self._make_loc_type(name="Regional Medical Store", parent_type=region)
        self._make_loc_type(name="Regional Hospital", parent_type=region)

        district = self._make_loc_type(name="district", administrative=True,
                                       parent_type=region)
        self._make_loc_type(name="Clinic", parent_type=district)
        self._make_loc_type(name="District Hospital", parent_type=district)
        self._make_loc_type(name="Health Centre", parent_type=district)
        self._make_loc_type(name="CHPS Facility", parent_type=district)
        self._make_loc_type(name="Hospital", parent_type=district)
        self._make_loc_type(name="Psychiatric Hospital", parent_type=district)
        self._make_loc_type(name="Polyclinic", parent_type=district)
        self._make_loc_type(name="facility", parent_type=district)

        config = CommtrackConfig.for_domain(self.domain)
        config.consumption_config.exclude_invalid_periods = True
        config.save()

    def _create_or_edit_facility_manager_role(self):
        facility_manager_role = UserRole.by_domain_and_name(self.domain, 'Facility manager')
        reports_list = [
            "corehq.apps.reports.standard.sms.MessageLogReport",
            "custom.ewsghana.reports.specific_reports.dashboard_report.DashboardReport",
            "custom.ewsghana.reports.specific_reports.stock_status_report.StockStatus",
            "custom.ewsghana.reports.specific_reports.reporting_rates.ReportingRatesReport",
            "custom.ewsghana.reports.maps.EWSMapReport"
        ]
        if facility_manager_role:
            permissions = Permissions(
                edit_web_users=True,
                edit_commcare_users=True,
                view_reports=False,
                view_report_list=reports_list
            )
            facility_manager_role[0].permissions = permissions
            facility_manager_role[0].save()
        else:

            role = UserRole(
                domain=self.domain,
                permissions=Permissions(
                    view_reports=False,
                    edit_web_users=True,
                    edit_commcare_users=True,
                    view_report_list=reports_list
                ),
                name='Facility manager'
            )
            role.save()

    def _create_or_edit_administrator_role(self):
        administrator_role = UserRole.by_domain_and_name(self.domain, 'Administrator')
        reports_list = [
            "corehq.apps.reports.standard.sms.MessageLogReport",
            "custom.ewsghana.reports.specific_reports.dashboard_report.DashboardReport",
            "custom.ewsghana.reports.specific_reports.stock_status_report.StockStatus",
            "custom.ewsghana.reports.specific_reports.reporting_rates.ReportingRatesReport",
            "custom.ewsghana.reports.maps.EWSMapReport",
            "custom.ewsghana.reports.email_reports.CMSRMSReport",
            "custom.ewsghana.reports.email_reports.StockSummaryReport",
            "custom.ewsghana.comparison_report.ProductsCompareReport",
            "custom.ewsghana.comparison_report.LocationsCompareReport",
            "custom.ewsghana.comparison_report.SupplyPointsCompareReport",
            "custom.ewsghana.comparison_report.WebUsersCompareReport",
            "custom.ewsghana.comparison_report.SMSUsersCompareReport"
        ]

        if administrator_role:
            permissions = Permissions(
                edit_web_users=True,
                edit_commcare_users=True,
                view_reports=False,
                view_report_list=reports_list
            )
            administrator_role[0].permissions = permissions
            administrator_role[0].save()
        else:
            role = UserRole(
                domain=self.domain,
                permissions=Permissions(
                    view_reports=False,
                    edit_web_users=True,
                    edit_commcare_users=True,
                    view_report_list=reports_list
                ),
                name='Administrator'
            )
            role.save()

    def _edit_read_only_role(self):
        read_only_role = UserRole.get_read_only_role_by_domain(self.domain)
        read_only_role.permissions.view_report_list = [
            "corehq.apps.reports.standard.sms.MessageLogReport",
            "custom.ewsghana.reports.specific_reports.dashboard_report.DashboardReport",
            "custom.ewsghana.reports.specific_reports.stock_status_report.StockStatus",
            "custom.ewsghana.reports.specific_reports.reporting_rates.ReportingRatesReport",
            "custom.ewsghana.reports.maps.EWSMapReport"
        ]
        read_only_role.permissions.view_reports = False
        read_only_role.save()

    def _create_or_edit_web_reporter_role(self):
        web_reporter_roles = UserRole.by_domain_and_name(self.domain, 'Web Reporter')
        report_list = [
            "corehq.apps.reports.standard.sms.MessageLogReport",
            "custom.ewsghana.reports.specific_reports.dashboard_report.DashboardReport",
            "custom.ewsghana.reports.specific_reports.stock_status_report.StockStatus",
            "custom.ewsghana.reports.specific_reports.reporting_rates.ReportingRatesReport",
            "custom.ewsghana.reports.maps.EWSMapReport"
        ]
        if web_reporter_roles:
            web_reporter_role = web_reporter_roles[0]
            web_reporter_role.permissions.view_reports = False
            web_reporter_role.permissions.view_report_list = report_list
            web_reporter_role.save()
        else:
            role = UserRole(
                domain=self.domain,
                permissions=Permissions(
                    view_reports=False,
                    view_report_list=report_list
                ),
                name='Web Reporter'
            )
            role.save()

    def create_or_edit_roles(self):
        self._create_or_edit_facility_manager_role()
        self._create_or_edit_administrator_role()
        self._create_or_edit_web_reporter_role()
        self._edit_read_only_role()

    def product_sync(self, ews_product):
        product = super(EWSApi, self).product_sync(ews_product)
        ews_product_extension(product, ews_product)
        return product

    def _set_location_properties(self, location, ews_location):
        location.domain = self.domain
        location.name = ews_location.name
        location.metadata = {}
        if ews_location.latitude:
            location.latitude = float(ews_location.latitude)
        if ews_location.longitude:
            location.longitude = float(ews_location.longitude)
        location.location_type = ews_location.type
        location.site_code = ews_location.code
        location.external_id = str(ews_location.id)

    def _set_up_supply_point(self, location, ews_location):
        if location.location_type in ['country', 'region', 'district']:
            supply_point_with_stock_data = filter(
                lambda x: x.last_reported and x.active, ews_location.supply_points
            )
            location.save()
            for supply_point in supply_point_with_stock_data:
                created_location = self._create_location_from_supply_point(supply_point, location)
                fake_location = Loc(
                    _id=created_location._id,
                    name=supply_point.name,
                    external_id=str(supply_point.id),
                    domain=self.domain
                )
                case = SupplyPointCase.get_or_create_by_location(fake_location)
                sql_location = created_location.sql_location
                sql_location.supply_point_id = case.get_id
                sql_location.save()
        elif ews_location.supply_points:
            active_supply_points = filter(lambda sp: sp.active, ews_location.supply_points)
            if active_supply_points:
                supply_point = active_supply_points[0]
            else:
                supply_point = ews_location.supply_points[0]
            location.name = supply_point.name
            location.site_code = supply_point.code
            if supply_point.code in TEACHING_HOSPITALS:
                location.location_type = 'Teaching Hospital'
                location.lineage = location.lineage[1:]
            else:
                location.location_type = supply_point.type
            try:
                sql_location = SQLLocation.objects.get(domain=self.domain, site_code=supply_point.code)
                if not sql_location.location_type.administrative:
                    raise MigrationException(
                        u'Site code {} is already used by {}'.format(supply_point.code, sql_location.name)
                    )
                couch_location = sql_location.couch_location
                couch_location.site_code = None
                couch_location.save()
            except SQLLocation.DoesNotExist:
                pass
            location.save()
            supply_point = self._create_supply_point_from_location(supply_point, location)
            if supply_point:
                sql_location = location.sql_location
                sql_location.supply_point_id = supply_point.get_id
                sql_location.save()
        else:
            location.save()
            fake_location = Loc(
                _id=location.get_id,
                name=location.name,
                external_id=None,
                domain=self.domain
            )
            supply_point = SupplyPointCase.get_or_create_by_location(fake_location)
            sql_location = location.sql_location
            sql_location.supply_point_id = supply_point.get_id
            sql_location.save()
            location.archive()

    def _sync_parent(self, parent_id):
        parent = self.endpoint.get_location(parent_id)
        loc_parent = self.location_sync(Location(parent))
        return loc_parent.get_id

    def _set_in_charges(self, ews_user_id, location):
        sms_user = self.sms_user_sync(self.endpoint.get_smsuser(ews_user_id))
        FacilityInCharge.objects.get_or_create(
            location=location,
            user_id=sms_user.get_id
        )

    def location_sync(self, ews_location):
        try:
            sql_loc = SQLLocation.objects.get(
                domain=self.domain,
                external_id=int(ews_location.id)
            )
            location = Loc.get(sql_loc.location_id)
        except SQLLocation.DoesNotExist:
            location = None
        if not location:
            if ews_location.parent_id:
                try:
                    loc_parent = SQLLocation.objects.get(
                        external_id=ews_location.parent_id,
                        domain=self.domain
                    )
                    loc_parent_id = loc_parent.location_id
                except SQLLocation.DoesNotExist:
                    loc_parent_id = self._sync_parent(ews_location.parent_id)

                location = Loc(parent=loc_parent_id)
            else:
                location = Loc()
                location.lineage = []

            self._set_location_properties(location, ews_location)
            self._set_up_supply_point(location, ews_location)
        else:
            location_dict = {}
            if location.sql_location.location_type.administrative:
                location_dict = {
                    'name': ews_location.name,
                    'latitude': float(ews_location.latitude) if ews_location.latitude else None,
                    'longitude': float(ews_location.longitude) if ews_location.longitude else None,
                }
                try:
                    SQLLocation.objects.get(domain=self.domain, site_code=ews_location.code.lower())
                except SQLLocation.DoesNotExist:
                    location_dict['site_code'] = ews_location.code.lower()
            else:
                supply_point_with_stock_data = filter(
                    lambda x: x.last_reported and x.active, ews_location.supply_points
                )
                supply_point = None
                if supply_point_with_stock_data:
                    supply_point = supply_point_with_stock_data[0]
                elif ews_location.supply_points:
                    supply_point = ews_location.supply_points[0]

                if supply_point:
                    location_dict = {
                        'name': supply_point.name,
                        'latitude': float(ews_location.latitude) if ews_location.latitude else None,
                        'longitude': float(ews_location.longitude) if ews_location.longitude else None,
                        'site_code': supply_point.code,
                    }

            if location_dict and apply_updates(location, location_dict):
                location.save()
        for supply_point in ews_location.supply_points:
            sp = get_supply_point_case_by_domain_external_id(self.domain, supply_point.id)
            if sp:
                sql_location = sp.sql_location
                if set(sql_location.products.values_list('code', flat=True)) != supply_point.products:
                    sql_location.products = SQLProduct.objects.filter(
                        domain=self.domain,
                        code__in=supply_point.products
                    )
                    sql_location.save()

                for in_charge in supply_point.incharges:
                    self._set_in_charges(in_charge, sql_location)
        return location

    def web_user_sync(self, ews_webuser):
        username = ews_webuser.email.lower()
        if not username:
            try:
                validate_email(ews_webuser.username)
                username = ews_webuser.username
            except ValidationError:
                return None
        user = WebUser.get_by_username(username)
        user_dict = {
            'first_name': ews_webuser.first_name,
            'last_name': ews_webuser.last_name,
            'is_active': ews_webuser.is_active,
            'last_login': force_to_datetime(ews_webuser.last_login),
            'date_joined': force_to_datetime(ews_webuser.date_joined),
            'password_hashed': True,
        }
        sql_location = None
        location_id = None
        if ews_webuser.location:
            try:
                sql_location = SQLLocation.objects.get(domain=self.domain, external_id=ews_webuser.location)
                location_id = sql_location.location_id
            except SQLLocation.DoesNotExist:
                pass

        if user is None:
            try:
                user = WebUser.create(domain=None, username=username,
                                      password=ews_webuser.password, email=ews_webuser.email.lower(),
                                      **user_dict)
                user.add_domain_membership(self.domain, location_id=location_id)
            except Exception as e:
                logging.error(e)
        else:
            if self.domain not in user.get_domains():
                user.add_domain_membership(self.domain, location_id=location_id)

        ews_webuser_extension(user, ews_webuser)
        dm = user.get_domain_membership(self.domain)

        if dm.location_id != location_id:
            dm.location_id = location_id

        if ews_webuser.contact:
            contact = self.sms_user_sync(ews_webuser.contact)
            if sql_location:
                contact.set_location(sql_location.couch_location)
                contact.save()

        if ews_webuser.is_superuser:
            dm.role_id = UserRole.by_domain_and_name(self.domain, 'Administrator')[0].get_id
        elif ews_webuser.groups and ews_webuser.groups[0].name == 'facility_manager':
            dm.role_id = UserRole.by_domain_and_name(self.domain, 'Facility manager')[0].get_id
        else:
            if ews_webuser.supply_point:
                supply_point = get_supply_point_case_by_domain_external_id(self.domain, ews_webuser.supply_point)
                if supply_point:
                    dm.location_id = supply_point.location_id
                    dm.role_id = UserRole.by_domain_and_name(self.domain, 'Web Reporter')[0].get_id
                else:
                    dm.role_id = UserRole.get_read_only_role_by_domain(self.domain).get_id
            else:
                dm.role_id = UserRole.get_read_only_role_by_domain(self.domain).get_id
        user.save()
        return user

    def sms_user_sync(self, ews_smsuser, **kwargs):
        sms_user = super(EWSApi, self).sms_user_sync(ews_smsuser, **kwargs)
        if not sms_user:
            return None
        sms_user.user_data['to'] = ews_smsuser.to

        if ews_smsuser.role:
            sms_user.user_data['role'] = [ews_smsuser.role]

        sms_user.save()
        if ews_smsuser.supply_point:
            if ews_smsuser.supply_point.id:
                sp = get_supply_point_case_by_domain_external_id(self.domain, ews_smsuser.supply_point.id)
            else:
                sp = None

            if sp:
                couch_location = sp.location
            elif ews_smsuser.supply_point.location_id:
                try:
                    location = SQLLocation.objects.get(domain=self.domain,
                                                       external_id=ews_smsuser.supply_point.location_id)
                    couch_location = location.couch_location
                except SQLLocation.DoesNotExist:
                    couch_location = None
            else:
                couch_location = None
            if couch_location:
                sms_user.set_location(couch_location)
        return sms_user
