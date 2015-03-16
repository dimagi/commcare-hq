import logging
from django.core.validators import validate_email
from corehq.apps.products.models import SQLProduct
from custom.logistics.commtrack import add_location
from dimagi.utils.dates import force_to_datetime
from corehq import Domain
from corehq.apps.commtrack.models import SupplyPointCase
from corehq.apps.locations.models import SQLLocation
from corehq.apps.locations.schema import LocationType
from corehq.apps.users.models import WebUser, UserRole, Permissions
from custom.api.utils import apply_updates
from custom.ewsghana.extensions import ews_product_extension, ews_webuser_extension
from jsonobject.properties import StringProperty, BooleanProperty, ListProperty, IntegerProperty, ObjectProperty
from custom.ilsgateway.api import ProductStock, StockTransaction
from jsonobject import JsonObject
from custom.logistics.api import LogisticsEndpoint, APISynchronization
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

    def __init__(self, base_uri, username, password):
        super(GhanaEndpoint, self).__init__(base_uri, username, password)
        self.supply_point_url = self._urlcombine(self.base_uri, '/supplypoints/')

    def get_supply_points(self, **kwargs):
        meta, supply_points = self.get_objects(self.supply_point_url, **kwargs)
        return meta, [SupplyPoint(supply_point) for supply_point in supply_points]


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
            ]
        }
    ]
    PRODUCT_CUSTOM_FIELDS = []

    def _create_location_type_if_not_exists(self, supply_point, location):
        domain = Domain.get_by_name(self.domain)
        if not filter(lambda l: l.name == supply_point.type, domain.location_types):
            domain.location_types.append(LocationType(
                name=supply_point.type,
                allowed_parents=[location.location_type],
                administrative=False
            ))
            domain.save()

    def _create_location_from_supply_point(self, supply_point, location):
        try:
            sql_location = SQLLocation.objects.get(domain=self.domain, site_code=supply_point.code)
            return Loc.get(sql_location.location_id)
        except SQLLocation.DoesNotExist:
            self._create_location_type_if_not_exists(supply_point, location)
            new_location = Loc(parent=location)
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
            SupplyPointCase.get_or_create_by_location(Loc(_id=location._id,
                                                          name=supply_point.name,
                                                          external_id=str(supply_point.id),
                                                          domain=self.domain))

    def prepare_commtrack_config(self):
        domain = Domain.get_by_name(self.domain)
        domain.location_types = [
            LocationType(name="country", allowed_parents=[""],
                         administrative=True),
            LocationType(name="Central Medical Store", allowed_parents=["country"],
                         administrative=False),
            LocationType(name="Teaching Hospital", allowed_parents=["country"],
                         administrative=False),
            LocationType(name="region", allowed_parents=["country"],
                         administrative=True),
            LocationType(name="Regional Medical Store", allowed_parents=["region"],
                         administrative=False),
            LocationType(name="Regional Hospital", allowed_parents=["region"],
                         administrative=False),
            LocationType(name="district", allowed_parents=["region"],
                         administrative=True),
            LocationType(name="Clinic", allowed_parents=["district"],
                         administrative=False),
            LocationType(name="District Hospital", allowed_parents=["district"],
                         administrative=False),
            LocationType(name="Health Centre", allowed_parents=["district"],
                         administrative=False),
            LocationType(name="CHPS Facility", allowed_parents=["district"],
                         administrative=False),
            LocationType(name="Hospital", allowed_parents=["district"],
                         administrative=False),
            LocationType(name="Psychiatric Hospital", allowed_parents=["district"],
                         administrative=False),
            LocationType(name="Polyclinic", allowed_parents=["district"],
                         administrative=False),
            LocationType(name="facility", allowed_parents=["district"],
                         administrative=False)
        ]
        domain.save()
        role = UserRole(
            domain=self.domain,
            permissions=Permissions(
                view_reports=True,
                edit_web_users=True,
                edit_commcare_users=True,
                edit_data=True
            ),
            name='Facility manager'
        )
        role.save()

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
        supply_point_with_stock_data = filter(lambda x: x.last_reported, ews_location.supply_points)
        if location.location_type in ['country', 'region', 'district']:
            for supply_point in supply_point_with_stock_data:
                created_location = self._create_location_from_supply_point(supply_point, location)
                fake_location = Loc(
                    _id=created_location._id,
                    name=supply_point.name,
                    external_id=str(supply_point.id),
                    domain=self.domain
                )
                SupplyPointCase.get_or_create_by_location(fake_location)
                created_location.save()
            fake_location = Loc(_id=location._id,
                                name=location.name,
                                domain=self.domain)
            SupplyPointCase.get_or_create_by_location(fake_location)
        elif ews_location.supply_points:
            supply_point = ews_location.supply_points[0]
            location.location_type = supply_point.type
            self._create_supply_point_from_location(supply_point, location)
            location.save()

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
                    parent = self.endpoint.get_location(ews_location.parent_id)
                    loc_parent = self.location_sync(Location(parent))
                    loc_parent_id = loc_parent._id

                location = Loc(parent=loc_parent_id)
            else:
                location = Loc()
                location.lineage = []

            self._set_location_properties(location, ews_location)
            location.save()
            self._set_up_supply_point(location, ews_location)
        else:
            location_dict = {
                'name': ews_location.name,
                'latitude': float(ews_location.latitude) if ews_location.latitude else None,
                'longitude': float(ews_location.longitude) if ews_location.longitude else None,
                'site_code': ews_location.code.lower(),
                'external_id': str(ews_location.id),
            }

            if apply_updates(location, location_dict):
                location.save()
            for loc in ews_location.supply_points:
                sp = SupplyPointCase.view('hqcase/by_domain_external_id',
                                          key=[self.domain, str(loc.id)],
                                          reduce=False,
                                          include_docs=True,
                                          limit=1).first()
                if sp:
                    sqlloc = sp.location.sql_location
                    sqlloc.stocks_all_products = False
                    if not sqlloc.products:
                        sqlloc.products = SQLProduct.objects.filter(domain=self.domain, code__in=loc.products)
                        sqlloc.save()
        return location

    def convert_web_user_to_sms_user(self, ews_webuser):
        sms_user = SMSUser()
        sms_user.username = ews_webuser.username
        sms_user.email = ews_webuser.email

        if ews_webuser.contact and ews_webuser.contact.supply_point:
            sms_user.supply_point = ews_webuser.contact.supply_point
        elif ews_webuser.location:
            sms_user.supply_point = SupplyPoint(
                location_id=ews_webuser.location
            )

        sms_user.is_active = str(ews_webuser.is_active)
        sms_user.name = ews_webuser.first_name + " " + ews_webuser.last_name
        if ews_webuser.contact:
            sms_user.backend = ews_webuser.contact.backend
            sms_user.to = ews_webuser.contact.to
            sms_user.phone_numbers = ews_webuser.contact.phone_numbers
        return self.sms_user_sync(
            sms_user,
            username_part=ews_webuser.username.lower() if ews_webuser.username else None,
            password=ews_webuser.password,
            first_name=ews_webuser.first_name,
            last_name=ews_webuser.last_name
        )

    def web_user_sync(self, ews_webuser):
        if not ews_webuser.is_superuser and ews_webuser.groups:
            group = ews_webuser.groups[0]
            if group.name == 'facility_manager':
                return self.convert_web_user_to_sms_user(ews_webuser)

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
        sp = SupplyPointCase.view('hqcase/by_domain_external_id',
                                  key=[self.domain, str(ews_webuser.location)],
                                  reduce=False,
                                  include_docs=True,
                                  limit=1).first()
        location_id = sp.location_id if sp else None

        if user is None:
            try:
                user = WebUser.create(domain=None, username=username,
                                      password=ews_webuser.password, email=ews_webuser.email,
                                      **user_dict)
                user.add_domain_membership(self.domain, location_id=location_id)
            except Exception as e:
                logging.error(e)
        else:
            if self.domain not in user.get_domains():
                user.add_domain_membership(self.domain, location_id=location_id)
        ews_webuser_extension(user, ews_webuser)
        dm = user.get_domain_membership(self.domain)
        if ews_webuser.is_superuser:
            dm.is_admin = True
        else:
            dm.role_id = UserRole.get_read_only_role_by_domain(self.domain).get_id
        user.save()
        return user

    def sms_user_sync(self, ews_smsuser, **kwargs):
        sms_user = super(EWSApi, self).sms_user_sync(ews_smsuser, **kwargs)
        if not sms_user:
            return None
        sms_user.user_data['to'] = ews_smsuser.to

        if ews_smsuser.supply_point:
            if ews_smsuser.supply_point.id:
                sp = SupplyPointCase.view('hqcase/by_domain_external_id',
                                          key=[self.domain, str(ews_smsuser.supply_point.id)],
                                          reduce=False,
                                          include_docs=True,
                                          limit=1).first()
            else:
                sp = None

            if sp:
                couch_location_id = sp.location_id
            elif ews_smsuser.supply_point.location_id:
                try:
                    location = SQLLocation.objects.get(domain=self.domain,
                                                       external_id=ews_smsuser.supply_point.location_id)
                    couch_location_id = location.location_id
                except SQLLocation.DoesNotExist:
                    couch_location_id = None
            else:
                couch_location_id = None
            if couch_location_id:
                dm = sms_user.get_domain_membership(self.domain)
                dm.location_id = couch_location_id
                sms_user.save()
                add_location(sms_user, couch_location_id)

        if ews_smsuser.role == 'facility_manager':
            role = UserRole.by_domain_and_name(self.domain, 'Facility manager')
            if role:
                dm = sms_user.get_domain_membership(self.domain)
                dm.role_id = role[0].get_id

        sms_user.save()
        return sms_user
