from corehq import Domain
from corehq.apps.commtrack.models import SupplyPointCase
from corehq.apps.locations.models import SQLLocation
from corehq.apps.locations.schema import LocationType
from corehq.apps.users.models import UserRole
from custom.api.utils import apply_updates
from custom.ewsghana import LOCATION_TYPES
from custom.ewsghana.extensions import ews_smsuser_extension, ews_webuser_extension, ews_product_extension
from jsonobject.properties import StringProperty, BooleanProperty, ListProperty, IntegerProperty, ObjectProperty
from custom.ilsgateway.api import ProductStock, StockTransaction
from jsonobject import JsonObject
from custom.logistics.api import LogisticsEndpoint, APISynchronization
from corehq.apps.locations.models import Location as Loc
from custom.logistics.commtrack import add_location


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


class SupplyPoint(JsonObject):
    id = IntegerProperty()
    code = StringProperty()
    groups = ListProperty()
    last_reported = StringProperty()
    name = StringProperty()
    primary_reporter = IntegerProperty()
    supervised_by = IntegerProperty()
    supplied_by = IntegerProperty()
    type = StringProperty()


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


class EWSApi(APISynchronization):

    def prepare_commtrack_config(self):
        domain = Domain.get_by_name(self.domain)
        domain.location_types = []
        for i, value in enumerate(LOCATION_TYPES):
            if not any(lt.name == value
                       for lt in domain.location_types):
                allowed_parents = [LOCATION_TYPES[i - 1]] if i > 0 else [""]
                domain.location_types.append(
                    LocationType(name=value, allowed_parents=allowed_parents,
                                 administrative=(value.lower() != 'facility')))

        domain.location_types.append(LocationType(
            name='regional warehouse',
            allowed_parents=['region'],
            administrative=False
        ))

        domain.location_types.append(LocationType(
            name='national warehouse',
            allowed_parents=['country'],
            administrative=False
        ))
        domain.save()
        try:
            SQLLocation.objects.get(domain=self.domain, site_code='default_location')
        except SQLLocation.DoesNotExist:
            location = Loc(
                name='Default location',
                location_type='facility',
                domain=self.domain,
                site_code='default_location'
            )
            location.save()
            SupplyPointCase.create_from_location(domain=self.domain, location=location)

    def products_sync(self, ews_product):
        product = super(EWSApi, self).products_sync(ews_product)
        ews_product_extension(product, ews_product)
        return product

    def locations_sync(self, ews_location):
        try:
            sql_loc = SQLLocation.objects.get(
                domain=self.domain,
                external_id=int(ews_location.id)
            )
            location = Loc.get(sql_loc.location_id)
        except SQLLocation.DoesNotExist:
            location = None
        except SQLLocation.MultipleObjectsReturned:
            return

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
                    loc_parent = self.locations_sync(Location(parent))
                    loc_parent_id = loc_parent._id

                location = Loc(parent=loc_parent_id)
                if ews_location.type == 'facility':
                    if loc_parent.location_type == 'region':
                        ews_location.type = 'regional warehouse'
                    elif loc_parent.location_type == 'country':
                        ews_location.type = 'national warehouse'
            else:
                location = Loc()
                location.lineage = []
            location.domain = self.domain
            location.name = ews_location.name
            location.metadata = {}
            if ews_location.groups:
                location.metadata['groups'] = ews_location.groups
            if ews_location.latitude:
                location.latitude = float(ews_location.latitude)
            if ews_location.longitude:
                location.longitude = float(ews_location.longitude)
            location.location_type = ews_location.type
            location.site_code = ews_location.code
            location.external_id = str(ews_location.id)
            location.save()

            supply_points = filter(lambda x: x.last_reported, ews_location.supply_points)
            if len(supply_points) > 1:
                for supply_point in supply_points:
                    domain = Domain.get_by_name(self.domain)
                    if not filter(lambda l: l.name == supply_point.type, domain.location_types):
                        domain.location_types.append(LocationType(
                            name=supply_point.type,
                            allowed_parents=[location.location_type],
                            administrative=False
                        ))
                        domain.save()
                    new_location = Loc(parent=location)
                    new_location.domain = self.domain
                    new_location.location_type = supply_point.type
                    new_location.name = supply_point.name
                    new_location.site_code = supply_point.code
                    if supply_point.supervised_by:
                        new_location.metadata['supervised_by'] = supply_point.supervised_by
                    new_location.save()

                    new_location.external_id = str(supply_point.id)
                    SupplyPointCase.create_from_location(self.domain, new_location)
            elif supply_points:
                supply_point = supply_points[0]
                if not SupplyPointCase.get_by_location(location):
                    if supply_point.supervised_by:
                        location.metadata['supervised_by'] = supply_point.supervised_by
                        location.save()
                    sp = SupplyPointCase.create_from_location(self.domain, location)
                    sp.external_id = str(supply_point.id)
                    sp.save()
        else:
            location_dict = {
                'name': ews_location.name,
                'latitude': float(ews_location.latitude) if ews_location.latitude else None,
                'longitude': float(ews_location.longitude) if ews_location.longitude else None,
                'site_code': ews_location.code.lower(),
                'external_id': str(ews_location.id),
            }
            if ews_location.groups:
                location_dict['metadata']['groups'] = ews_location.groups

            if apply_updates(location, location_dict):
                location.save()

        for supply_point in ews_location.supply_points:
                sp = SupplyPointCase.view('hqcase/by_domain_external_id',
                                          key=[self.domain, str(supply_point.id)],
                                          reduce=False,
                                          include_docs=True,
                                          limit=1).first()
                if sp:
                    if location._id == sp.location_id:
                        location_from_sp = location
                    else:
                        location_from_sp = sp.location
                    location_from_sp.metadata['supply_point_type'] = supply_point.type
                    location_from_sp.save()
        return location

    def web_users_sync(self, ews_webuser):
        web_user = super(EWSApi, self).web_users_sync(ews_webuser)
        if not web_user:
            return None
        ews_webuser_extension(web_user, ews_webuser)
        dm = web_user.get_domain_membership(self.domain)
        if ews_webuser.is_superuser:
            dm.is_admin = True
        else:
            dm.role_id = UserRole.get_read_only_role_by_domain(self.domain).get_id
        web_user.save()
        return web_user

    def sms_users_sync(self, ews_smsuser):
        sms_user = super(EWSApi, self).sms_users_sync(ews_smsuser)
        ews_smsuser_extension(sms_user, ews_smsuser)
        dm = sms_user.get_domain_membership(self.domain)
        if not dm.location_id:
            try:
                location = SQLLocation.objects.get(domain=self.domain, site_code='default_location')
            except SQLLocation.DoesNotExist:
                return sms_user
            dm = sms_user.get_domain_membership(self.domain)
            dm.location_id = location.location_id
            sms_user.save()
            add_location(sms_user, location.location_id)
        return sms_user
