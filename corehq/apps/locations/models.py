from __future__ import absolute_import
from __future__ import unicode_literals
import uuid
from datetime import datetime
from functools import partial, wraps

from bulk_update.helper import bulk_update as bulk_update_helper

import jsonfield
from django.db import models, transaction
from django_cte import CTEQuerySet
from memoized import memoized
from mptt.models import TreeForeignKey

from corehq.form_processor.interfaces.supply import SupplyInterface
from corehq.form_processor.exceptions import CaseNotFound
from corehq.apps.domain.models import Domain
from corehq.apps.locations.adjacencylist import AdjListModel, AdjListManager
from corehq.apps.locations.queryutil import ComparedQuerySet
from corehq.apps.products.models import SQLProduct
from corehq.toggles import LOCATION_TYPE_STOCK_RATES


class LocationTypeManager(models.Manager):

    def full_hierarchy(self, domain):
        """
        Returns a graph of the form
        {
           '<loc_type_id>: (
               loc_type,
               {'<child_loc_type_id>': (child_loc_type, [...])}
           )
        }
        """
        hierarchy = {}

        def insert_loc_type(loc_type):
            """
            Get parent location's hierarchy, insert loc_type into it, and return
            hierarchy below loc_type
            """
            if not loc_type.parent_type:
                lt_hierarchy = hierarchy
            else:
                lt_hierarchy = insert_loc_type(loc_type.parent_type)
            if loc_type.id not in lt_hierarchy:
                lt_hierarchy[loc_type.id] = (loc_type, {})
            return lt_hierarchy[loc_type.id][1]

        for loc_type in self.filter(domain=domain).all():
            insert_loc_type(loc_type)

        return hierarchy

    def by_domain(self, domain):
        """
        Sorts location types by hierarchy
        """
        ordered_loc_types = []

        def step_through_graph(hierarchy):
            for _, (loc_type, children) in hierarchy.items():
                ordered_loc_types.append(loc_type)
                step_through_graph(children)

        step_through_graph(self.full_hierarchy(domain))
        return ordered_loc_types


StockLevelField = partial(models.DecimalField, max_digits=10, decimal_places=1)


@memoized
def stock_level_config_for_domain(domain, commtrack_enabled):
    from corehq.apps.commtrack.models import CommtrackConfig
    ct_config = CommtrackConfig.for_domain(domain)
    if (
        (ct_config is None) or
        (not commtrack_enabled) or
        LOCATION_TYPE_STOCK_RATES.enabled(domain)
    ):
        return None
    else:
        return ct_config.stock_levels_config


class LocationType(models.Model):
    domain = models.CharField(max_length=255, db_index=True)
    name = models.CharField(max_length=255)
    code = models.SlugField(db_index=False, null=True)
    parent_type = models.ForeignKey('self', null=True, on_delete=models.CASCADE)
    administrative = models.BooleanField(default=False)
    shares_cases = models.BooleanField(default=False)
    view_descendants = models.BooleanField(default=False)

    # Sync optimization controls
    _expand_from = models.ForeignKey(
        'self',
        null=True,
        related_name='+',
        db_column='expand_from',
        on_delete=models.CASCADE,
    )  # levels below this location type that we start expanding from
    _expand_from_root = models.BooleanField(default=False, db_column='expand_from_root')
    expand_to = models.ForeignKey('self', null=True, related_name='+', on_delete=models.CASCADE)  # levels above this type that are synced
    include_without_expanding = models.ForeignKey(
        'self',
        null=True,
        related_name='+',
        on_delete=models.SET_NULL,
    )  # include all levels of this type and their ancestors
    # If specified, include only the linked types
    include_only = models.ManyToManyField('self', symmetrical=False, related_name='included_in')

    last_modified = models.DateTimeField(auto_now=True)
    has_user = models.BooleanField(default=False)

    emergency_level = StockLevelField(default=0.5)
    understock_threshold = StockLevelField(default=1.5)
    overstock_threshold = StockLevelField(default=3.0)

    objects = LocationTypeManager()

    class Meta(object):
        app_label = 'locations'
        unique_together = (
            ('domain', 'code'),
            ('domain', 'name'),
        )

    def __init__(self, *args, **kwargs):
        super(LocationType, self).__init__(*args, **kwargs)
        self._administrative_old = self.administrative
        self._has_user_old = self.has_user

    @property
    def expand_from(self):
        return self._expand_from

    @expand_from.setter
    def expand_from(self, value):
        if self._expand_from_root is True:
            self._expand_from_root = False
        self._expand_from = value

    @property
    def expand_from_root(self):
        return self._expand_from_root

    @expand_from_root.setter
    def expand_from_root(self, value):
        if self._expand_from_root is False and value is True:
            self._expand_from = None
        self._expand_from_root = value

    @property
    @memoized
    def commtrack_enabled(self):
        return Domain.get_by_name(self.domain).commtrack_enabled

    def _populate_stock_levels(self, config):
        self.emergency_level = config.emergency_level
        self.understock_threshold = config.understock_threshold
        self.overstock_threshold = config.overstock_threshold

    def save(self, *args, **kwargs):
        from .tasks import update_location_users

        if not self.code:
            from corehq.apps.commtrack.util import unicode_slug
            self.code = unicode_slug(self.name)
        if not self.commtrack_enabled:
            self.administrative = True

        config = stock_level_config_for_domain(self.domain, self.commtrack_enabled)
        if config:
            self._populate_stock_levels(config)

        is_not_first_save = self.pk is not None
        saved = super(LocationType, self).save(*args, **kwargs)

        if is_not_first_save:
            self.sync_administrative_status()
            if self._has_user_old != self.has_user:
                update_location_users.delay(self)

        return saved

    def sync_administrative_status(self, sync_supply_points=True):
        from .tasks import sync_administrative_status
        if self._administrative_old != self.administrative:
            sync_administrative_status.delay(self, sync_supply_points=sync_supply_points)
            self._administrative_old = self.administrative

    def __unicode__(self):
        return self.name

    def __repr__(self):
        return "LocationType(domain='{}', name='{}', administrative={})".format(
            self.domain,
            self.name,
            self.administrative,
        ).encode('utf-8')

    @property
    @memoized
    def can_have_children(self):
        return LocationType.objects.filter(parent_type=self).exists()

    @classmethod
    def _pre_bulk_save(cls, objects):
        if not objects:
            return

        commtrack_enabled = objects[0].commtrack_enabled
        if not commtrack_enabled:
            for o in objects:
                o.administrative = True

        domain = objects[0].domain
        stock_config = stock_level_config_for_domain(domain, commtrack_enabled)
        if stock_config:
            for o in objects:
                o._populate_stock_levels(stock_config)

    @classmethod
    def bulk_create(cls, objects):
        # 'objects' is a list of new LocationType objects to be created
        if not objects:
            return []

        cls._pre_bulk_save(objects)
        cls.objects.bulk_create(objects)
        return list(objects)

    @classmethod
    def bulk_update(cls, objects):
        # 'objects' is a list of existing LocationType objects to be updated
        # Note: this is tightly coupled with .bulk_management.NewLocationImporter.bulk_commit()
        #       so it can't be used on its own
        cls._pre_bulk_save(objects)
        now = datetime.utcnow()
        for o in objects:
            o.last_modified = now
        # the caller should call 'sync_administrative_status' for individual objects
        bulk_update_helper(objects)

    @classmethod
    def bulk_delete(cls, objects):
        # Given a list of existing SQL objects, bulk delete them
        if not objects:
            return
        ids = [o.id for o in objects]
        cls.objects.filter(id__in=ids).delete()


class LocationQueriesMixin(object):

    def location_ids(self):
        return self.values_list('location_id', flat=True)

    def accessible_to_user(self, domain, user):
        if user.has_permission(domain, 'access_all_locations'):
            return self.filter(domain=domain)

        assigned_location_ids = user.get_location_ids(domain)
        if not assigned_location_ids:
            return self.none()  # No locations are assigned to this user

        ids_query = SQLLocation.objects.get_locations_and_children(assigned_location_ids)
        assert isinstance(ids_query, ComparedQuerySet), ids_query
        return ComparedQuerySet(
            self.filter(id__in=ids_query._mptt_set),
            self.filter(id__in=ids_query._cte_set) if ids_query._cte_set is not None else None,
            ids_query,
        )

    def delete(self, *args, **kwargs):
        from .document_store import publish_location_saved
        for domain, location_id in self.values_list('domain', 'location_id'):
            publish_location_saved(domain, location_id, is_deletion=True)
        return super(LocationQueriesMixin, self).delete(*args, **kwargs)

    def _user_input_filter(self, domain, user_input):
        """Build a Q expression for filtering on user input

        Accepts partial matches, matches against name and site_code.
        """
        Q = models.Q
        return Q(domain=domain) & Q(
            Q(name__icontains=user_input) | Q(site_code__icontains=user_input)
        )

    def filter_by_user_input(self, domain, user_input):
        """
        Accepts partial matches, matches against name and site_code.
        """
        return self.filter(self._user_input_filter(domain, user_input))


class LocationQuerySet(LocationQueriesMixin, CTEQuerySet):
    pass


def location_queryset(func):
    @wraps(func)
    def wrapper(self, *args, **kw):
        result = func(self, *args, **kw)
        if type(result) == CTEQuerySet:
            result.__class__ = LocationQuerySet
        return result
    return wrapper


class LocationManager(LocationQueriesMixin, AdjListManager):

    @location_queryset
    def cte_get_ancestors(self, *args, **kw):
        return super(LocationManager, self).cte_get_ancestors(*args, **kw)

    @location_queryset
    def cte_get_descendants(self, *args, **kw):
        return super(LocationManager, self).cte_get_descendants(*args, **kw)

    def get_or_None(self, **kwargs):
        try:
            return self.get(**kwargs)
        except SQLLocation.DoesNotExist:
            return None

    def get_queryset(self):
        return (
            LocationQuerySet(self.model, using=self._db)
            .order_by(self.tree_id_attr, self.left_attr)  # mptt default
        )

    def get_from_user_input(self, domain, user_input):
        """
        First check by site-code, if that fails, fall back to name.
        Note that name lookup may raise MultipleObjectsReturned.
        """
        try:
            return self.get(domain=domain, site_code=user_input)
        except self.model.DoesNotExist:
            return self.get(domain=domain, name__iexact=user_input)

    def filter_path_by_user_input(self, domain, user_input):
        """
        Returns a queryset including all locations matching the user input
        and their children. This means "Middlesex" will match:
            Massachusetts/Middlesex
            Massachusetts/Middlesex/Boston
            Massachusetts/Middlesex/Cambridge
        It matches by name or site-code
        """
        direct_matches = self._user_input_filter(domain, user_input)
        return self.get_queryset_descendants(direct_matches, include_self=True)

    def get_locations(self, location_ids):
        return self.filter(location_id__in=location_ids)

    def get_locations_and_children(self, location_ids):
        """
        Takes a set of location ids and returns a django queryset of those
        locations and their children.
        """
        return self.get_queryset_descendants(
            self.filter(location_id__in=location_ids),
            include_self=True
        )

    def get_locations_and_children_ids(self, location_ids):
        return list(self.get_locations_and_children(location_ids).location_ids())


class OnlyUnarchivedLocationManager(LocationManager):

    def get_queryset(self):
        return (super(OnlyUnarchivedLocationManager, self).get_queryset()
                .filter(is_archived=False))

    def accessible_location_ids(self, domain, user):
        return list(self.accessible_to_user(domain, user).location_ids())


class OnlyArchivedLocationManager(LocationManager):

    def get_queryset(self):
        return (super(OnlyArchivedLocationManager, self).get_queryset()
                .filter(is_archived=True))

    def accessible_location_ids(self, domain, user):
        return list(self.accessible_to_user(domain, user).location_ids())


class SQLLocation(AdjListModel):
    domain = models.CharField(max_length=255, db_index=True)
    name = models.CharField(max_length=255, null=True)
    location_id = models.CharField(max_length=100, db_index=True, unique=True)
    location_type = models.ForeignKey(LocationType, on_delete=models.CASCADE)
    site_code = models.CharField(max_length=255)
    external_id = models.CharField(max_length=255, null=True, blank=True)
    metadata = jsonfield.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_modified = models.DateTimeField(auto_now=True)
    is_archived = models.BooleanField(default=False)
    latitude = models.DecimalField(max_digits=20, decimal_places=10, null=True, blank=True)
    longitude = models.DecimalField(max_digits=20, decimal_places=10, null=True, blank=True)
    parent = TreeForeignKey('self', null=True, blank=True, related_name='children', on_delete=models.CASCADE)

    # Use getter and setter below to access this value
    # since stocks_all_products can cause an empty list to
    # be what is stored for a location that actually has
    # all products available.
    _products = models.ManyToManyField(SQLProduct)
    stocks_all_products = models.BooleanField(default=True)

    supply_point_id = models.CharField(max_length=255, db_index=True, unique=True, null=True, blank=True)

    # For locations where location_type.has_user == True
    user_id = models.CharField(max_length=255, blank=True)

    objects = _tree_manager = LocationManager()
    # This should really be the default location manager
    active_objects = OnlyUnarchivedLocationManager()
    inactive_objects = OnlyArchivedLocationManager()

    def get_ancestor_of_type(self, type_code):
        """
        Returns the ancestor of given location_type_code of the location
        """
        try:
            return self.get_ancestors().get(location_type__code=type_code)
        except self.DoesNotExist:
            return None

    @classmethod
    def get_sync_fields(cls):
        return ["domain", "name", "site_code", "external_id",
                "metadata", "is_archived"]

    def save(self, *args, **kwargs):
        from corehq.apps.commtrack.models import sync_supply_point
        from .document_store import publish_location_saved

        if not self.location_id:
            self.location_id = uuid.uuid4().hex

        with transaction.atomic():
            set_site_code_if_needed(self)
            sync_supply_point(self)
            super(SQLLocation, self).save(*args, **kwargs)

        publish_location_saved(self.domain, self.location_id)

    def delete(self, *args, **kwargs):
        from corehq.apps.commtrack.models import sync_supply_point
        from .document_store import publish_location_saved
        to_delete = self.get_descendants(include_self=True)

        # This deletion should ideally happen in a transaction. It's not
        # currently possible as supply point cases are stored either in a
        # separate database or in couch. Happy Debugging!
        for loc in to_delete:
            loc._remove_users()
            sync_supply_point(loc, is_deletion=True)

        super(SQLLocation, self).delete(*args, **kwargs)
        publish_location_saved(self.domain, self.location_id, is_deletion=True)

    full_delete = delete

    def to_json(self, include_lineage=True):
        json_dict = {
            'name': self.name,
            'site_code': self.site_code,
            '_id': self.location_id,
            'location_id': self.location_id,
            'doc_type': 'Location',
            'domain': self.domain,
            'external_id': self.external_id,
            'is_archived': self.is_archived,
            'last_modified': self.last_modified.isoformat(),
            'latitude': float(self.latitude) if self.latitude else None,
            'longitude': float(self.longitude) if self.longitude else None,
            'metadata': self.metadata,
            'location_type': self.location_type.name,
            'location_type_code': self.location_type.code,
            'parent_location_id': self.parent_location_id,
        }
        if include_lineage:
            # lineage requires a non-trivial db hit
            json_dict['lineage'] = self.lineage
        return json_dict

    @property
    def lineage(self):
        return list(reversed(self.path[:-1]))

    _id = property(lambda self: self.location_id)
    get_id = property(lambda self: self.location_id)
    group_id = property(lambda self: self.location_id)

    @property
    def products(self):
        """
        If there are no products specified for this location, assume all
        products for the domain are relevant.
        """
        if self.stocks_all_products:
            return SQLProduct.by_domain(self.domain)
        else:
            return self._products.all()

    @products.setter
    def products(self, value):
        # this will set stocks_all_products to true if the user
        # has added all products in the domain to this location
        self.stocks_all_products = (set(value) ==
                                    set(SQLProduct.by_domain(self.domain)))

        self._products = value

    def _remove_users(self):
        """
        Unassigns the users assigned to that location.

        Used by both archive and delete methods
        """
        if self.user_id:
            from corehq.apps.users.models import CommCareUser
            user = CommCareUser.get(self.user_id)
            user.active = False
            user.save()

        _unassign_users_from_location(self.domain, self.location_id)
        self.update_users_at_ancestor_locations()

    def update_users_at_ancestor_locations(self):
        from . tasks import update_users_at_locations
        location_ids = list(self.get_ancestors().location_ids())
        update_users_at_locations.delay(location_ids)

    def archive(self):
        """
        Mark a location and its descendants as archived and unassigns users
        assigned to the location.
        """
        for loc in self.get_descendants(include_self=True):
            loc.is_archived = True
            loc.save()
            loc._remove_users()

    def unarchive(self):
        """
        Unarchive a location and reopen supply point case if it
        exists.
        """
        for loc in self.get_descendants(include_self=True):
            loc.is_archived = False
            loc.save()

            if loc.user_id:
                from corehq.apps.users.models import CommCareUser
                user = CommCareUser.get(loc.user_id)
                user.active = True
                user.save()

    class Meta(object):
        app_label = 'locations'
        unique_together = ('domain', 'site_code',)
        index_together = [
            ('tree_id', 'lft', 'rght')
        ]

    def __unicode__(self):
        return "{} ({})".format(self.name, self.domain)

    def __repr__(self):
        return "SQLLocation(domain='{}', name='{}', location_type='{}')".format(
            self.domain,
            self.name,
            self.location_type.name if hasattr(self, 'location_type') else None,
        ).encode('utf-8')

    @property
    def display_name(self):
        return "{} [{}]".format(self.name, self.location_type.name)

    def archived_descendants(self):
        """
        Returns a list of archived descendants for this location.
        """
        return self.get_descendants().filter(is_archived=True)

    def child_locations(self, include_archive_ancestors=False):
        """
        Returns a list of this location's children.
        """
        children = self.get_children()
        return filter_for_archived(children, include_archive_ancestors)

    @classmethod
    def root_locations(cls, domain, include_archive_ancestors=False):
        roots = cls.objects.root_nodes().filter(domain=domain)
        return filter_for_archived(roots, include_archive_ancestors)

    def get_path_display(self):
        return '/'.join(self.get_ancestors(include_self=True)
                            .values_list('name', flat=True))

    def get_case_sharing_groups(self, for_user_id=None):
        if self.location_type.shares_cases:
            yield self.case_sharing_group_object(for_user_id)
        if self.location_type.view_descendants:
            for sql_loc in self.get_descendants().filter(location_type__shares_cases=True, is_archived=False):
                yield sql_loc.case_sharing_group_object(for_user_id)

    def case_sharing_group_object(self, user_id=None):
        """
        Returns a fake group object that cannot be saved.

        This is used for giving users access via case sharing groups, without
        having a real group for every location that we have to manage/hide.
        """
        from corehq.apps.groups.models import UnsavableGroup

        group = UnsavableGroup(
            domain=self.domain,
            users=[user_id] if user_id else [],
            last_modified=datetime.utcnow(),
            name=self.get_path_display() + '-Cases',
            _id=self.location_id,
            case_sharing=True,
            reporting=False,
            metadata={
                'commcare_location_type': self.location_type.name,
                'commcare_location_name': self.name,
            },
        )

        for key, val in self.metadata.items():
            group.metadata['commcare_location_' + key] = val

        return group

    def is_direct_ancestor_of(self, location):
        return (location.get_ancestors(include_self=True)
                .filter(pk=self.pk).exists())

    @classmethod
    def by_domain(cls, domain):
        return cls.objects.filter(domain=domain)

    @property
    def path(self):
        try:
            return self._path
        except AttributeError:
            self._path = list(self.get_ancestors(include_self=True).location_ids())
        return self._path

    @path.setter
    def path(self, value):
        self._path = value

    @classmethod
    def by_location_id(cls, location_id):
        try:
            return cls.objects.get(location_id=location_id)
        except cls.DoesNotExist:
            return None

    # For quick_find compatability
    by_id = by_location_id

    def linked_supply_point(self):
        if not self.supply_point_id:
            return None
        try:
            return SupplyInterface(self.domain).get_supply_point(self.supply_point_id)
        except CaseNotFound:
            return None

    @property
    def parent_location_id(self):
        return self.parent.location_id if self.parent else None

    @property
    def location_type_object(self):
        return self.location_type

    @property
    def location_type_name(self):
        return self.location_type.name

    @property
    def sql_location(self):
        # For backwards compatability
        return self


def filter_for_archived(locations, include_archive_ancestors):
    """
    Perform filtering on a location queryset.

    include_archive_ancestors toggles between selecting only active
    children and selecting any child that is archived or has
    archived descendants.
    """
    if include_archive_ancestors:
        return [
            item for item in locations
            if item.is_archived or item.archived_descendants()
        ]
    else:
        return locations.filter(is_archived=False)


def make_location(**kwargs):
    """API compatabile with `Location.__init__`, but returns a SQLLocation"""
    loc_type_name = kwargs.pop('location_type')
    try:
        sql_location_type = LocationType.objects.get(
            domain=kwargs['domain'],
            name=loc_type_name,
        )
    except LocationType.DoesNotExist:
        msg = "You can't create a location without a real location type"
        raise LocationType.DoesNotExist(msg)
    kwargs['location_type'] = sql_location_type
    parent = kwargs.pop('parent', None)
    kwargs['parent'] = parent.sql_location if parent else None
    return SQLLocation(**kwargs)


def get_location(location_id, domain=None):
    """Drop-in replacement for `Location.get`, but returns a SQLLocation"""
    if domain:
        return SQLLocation.objects.get(domain=domain, location_id=location_id)
    else:
        return SQLLocation.objects.get(location_id=location_id)


def set_site_code_if_needed(location):
    from corehq.apps.commtrack.util import generate_code
    if not location.site_code:
        all_codes = [
            code.lower() for code in
            (SQLLocation.objects.exclude(location_id=location.location_id)
                                .filter(domain=location.domain)
                                .values_list('site_code', flat=True))
        ]
        location.site_code = generate_code(location.name, all_codes)


class LocationFixtureConfiguration(models.Model):
    domain = models.CharField(primary_key=True, max_length=255)
    sync_flat_fixture = models.BooleanField(default=True)
    sync_hierarchical_fixture = models.BooleanField(default=True)

    def __repr__(self):
        return '{}: flat: {}, hierarchical: {}'.format(
            self.domain, self.sync_flat_fixture, self.sync_hierarchical_fixture
        )

    @classmethod
    def for_domain(cls, domain):
        try:
            return cls.objects.get(domain=domain)
        except cls.DoesNotExist:
            return cls(domain=domain)


def _unassign_users_from_location(domain, location_id):
    """
    Unset location for all users assigned to that location.
    """
    from corehq.apps.locations.dbaccessors import user_ids_at_locations
    from corehq.apps.users.models import CommCareUser
    from dimagi.utils.couch.database import iter_docs

    user_ids = user_ids_at_locations([location_id])
    for doc in iter_docs(CommCareUser.get_db(), user_ids):
        user = CommCareUser.wrap(doc)
        if user.is_web_user():
            user.unset_location_by_id(domain, location_id, fall_back_to_next=True)
        elif user.is_commcare_user():
            user.unset_location_by_id(location_id, fall_back_to_next=True)
