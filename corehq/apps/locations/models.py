import warnings
from functools import partial

from bulk_update.helper import bulk_update as bulk_update_helper

from couchdbkit import ResourceNotFound
from dimagi.ext.couchdbkit import *
import itertools
from corehq.apps.cachehq.mixins import CachedCouchDocumentMixin
from dimagi.utils.couch.database import iter_docs
from dimagi.utils.couch.migration import SyncSQLToCouchMixin, SyncCouchToSQLMixin
from dimagi.utils.decorators.memoized import memoized
from datetime import datetime
from django.db import models, transaction
import jsonfield
from casexml.apps.case.cleanup import close_case
from corehq.form_processor.interfaces.supply import SupplyInterface
from corehq.form_processor.exceptions import CaseNotFound
from corehq.apps.commtrack.const import COMMTRACK_USERNAME
from corehq.apps.domain.models import Domain
from corehq.apps.products.models import SQLProduct
from corehq.toggles import LOCATION_TYPE_STOCK_RATES
from corehq.util.soft_assert import soft_assert
from mptt.models import MPTTModel, TreeForeignKey, TreeManager


LOCATION_REPORTING_PREFIX = 'locationreportinggroup-'


def notify_of_deprecation(msg):
    _assert = soft_assert(notify_admins=True, fail_if_debug=True)
    message = "Deprecated Locations feature used: {}".format(msg)
    _assert(False, message)


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
    last_modified = models.DateTimeField(auto_now=True)

    emergency_level = StockLevelField(default=0.5)
    understock_threshold = StockLevelField(default=1.5)
    overstock_threshold = StockLevelField(default=3.0)

    objects = LocationTypeManager()

    class Meta:
        app_label = 'locations'
        unique_together = (
            ('domain', 'code'),
            ('domain', 'name'),
        )

    def __init__(self, *args, **kwargs):
        super(LocationType, self).__init__(*args, **kwargs)
        self._administrative_old = self.administrative

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

        return saved

    def sync_administrative_status(self, sync_supply_points=True):
        from .tasks import sync_administrative_status
        if self._administrative_old != self.administrative:
            sync_administrative_status.delay(self, sync_supply_points=sync_supply_points)
            self._administrative_old = self.administrative

    def __unicode__(self):
        return self.name

    def __repr__(self):
        return u"LocationType(domain='{}', name='{}', administrative={})".format(
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
        domain = objects[0].domain
        names = [o.name for o in objects]
        cls.objects.bulk_create(objects)
        # we can return 'objects' directly without the below extra DB call after django 1.10,
        # which autosets 'id' attribute of all objects that are bulk created
        return list(cls.objects.filter(domain=domain, name__in=names))

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

    def couch_locations(self, wrapped=True):
        """
        Returns the couch locations corresponding to this queryset.
        """
        warnings.warn(
            "Converting SQLLocations to couch locations.  This should be "
            "used for backwards compatability only - not new features.",
            DeprecationWarning,
        )
        ids = self.location_ids()
        locations = iter_docs(Location.get_db(), ids)
        if wrapped:
            return itertools.imap(Location.wrap, locations)
        return locations

    def accessible_to_user(self, domain, user):
        if user.has_permission(domain, 'access_all_locations'):
            return self.filter(domain=domain)

        assigned_location_ids = user.get_location_ids(domain)
        if not assigned_location_ids:
            return self.none()  # No locations are assigned to this user
        return self.all() & SQLLocation.objects.get_locations_and_children(assigned_location_ids)

    def delete(self, *args, **kwargs):
        from .document_store import publish_location_saved
        for domain, location_id in self.values_list('domain', 'location_id'):
            publish_location_saved(domain, location_id, is_deletion=True)
        return super(LocationQueriesMixin, self).delete(*args, **kwargs)


class LocationQuerySet(LocationQueriesMixin, models.query.QuerySet):
    pass


class LocationManager(LocationQueriesMixin, TreeManager):

    def get_or_None(self, **kwargs):
        try:
            return self.get(**kwargs)
        except SQLLocation.DoesNotExist:
            return None

    def _get_base_queryset(self):
        return LocationQuerySet(self.model, using=self._db)

    def get_queryset(self):
        return (self._get_base_queryset()
                .order_by(self.tree_id_attr, self.left_attr))  # mptt default

    def get_from_user_input(self, domain, user_input):
        """
        First check by site-code, if that fails, fall back to name.
        Note that name lookup may raise MultipleObjectsReturned.
        """
        try:
            return self.get(domain=domain, site_code=user_input)
        except self.model.DoesNotExist:
            return self.get(domain=domain, name__iexact=user_input)

    def filter_by_user_input(self, domain, user_input):
        """
        Accepts partial matches, matches against name and site_code.
        """
        return (self.filter(domain=domain)
                    .filter(models.Q(name__icontains=user_input) |
                            models.Q(site_code__icontains=user_input)))

    def filter_path_by_user_input(self, domain, user_input):
        """
        Returns a queryset including all locations matching the user input
        and their children. This means "Middlesex" will match:
            Massachusetts/Middlesex
            Massachusetts/Middlesex/Boston
            Massachusetts/Middlesex/Cambridge
        It matches by name or site-code
        """
        direct_matches = self.filter_by_user_input(domain, user_input)
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


class SQLLocation(SyncSQLToCouchMixin, MPTTModel):
    domain = models.CharField(max_length=255, db_index=True)
    name = models.CharField(max_length=100, null=True)
    location_id = models.CharField(max_length=100, db_index=True, unique=True)
    _migration_couch_id_name = "location_id"  # Used for SyncSQLToCouchMixin
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

    objects = _tree_manager = LocationManager()
    # This should really be the default location manager
    active_objects = OnlyUnarchivedLocationManager()

    @classmethod
    def _migration_get_fields(cls):
        return ["domain", "name", "site_code", "external_id",
                "metadata", "is_archived"]

    @classmethod
    def _migration_get_couch_model_class(cls):
        return Location

    def _migration_do_sync(self):
        couch_obj = self._migration_get_or_create_couch_object()
        couch_obj._sql_location_type = self.location_type
        couch_obj.latitude = float(self.latitude) if self.latitude else None
        couch_obj.longitude = float(self.longitude) if self.longitude else None
        self._migration_sync_to_couch(couch_obj)

    @transaction.atomic()
    def save(self, *args, **kwargs):
        from corehq.apps.commtrack.models import sync_supply_point
        from .document_store import publish_location_saved
        self.supply_point_id = sync_supply_point(self)

        sync_to_couch = kwargs.pop('sync_to_couch', True)
        kwargs['sync_to_couch'] = False  # call it here
        super(SQLLocation, self).save(*args, **kwargs)
        if sync_to_couch:
            self._migration_do_sync()

        publish_location_saved(self.domain, self.location_id)

    def to_json(self):
        return {
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
            "lineage": self.lineage,
            'parent_location_id': self.parent_location_id,
        }

    @property
    def lineage(self):
        return list(self.get_ancestors(ascending=True).location_ids())

    # # A few aliases for location_id to be compatible with couch locs
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

    def _close_case_and_remove_users(self):
        """
        Closes linked supply point cases for a location and unassigns the users
        assigned to that location.

        Used by both archive and delete methods
        """
        sp = self.linked_supply_point()
        # sanity check that the supply point exists and is still open.
        # this is important because if you archive a child, then try
        # to archive the parent, we don't want to try to close again
        if sp and not sp.closed:
            close_case(sp.case_id, self.domain, COMMTRACK_USERNAME)

        _unassign_users_from_location(self.domain, self.location_id)

    def _archive_single_location(self):
        """
        Archive a single location, caller is expected to handle
        archiving children as well.

        This is just used to prevent having to do recursive
        couch queries in `archive()`.
        """
        self.is_archived = True
        self.save()

        self._close_case_and_remove_users()

    def archive(self):
        """
        Mark a location and its descendants as archived.
        This will cause it (and its data) to not show up in default Couch and
        SQL views.  This also unassigns users assigned to the location.
        """
        for loc in self.get_descendants(include_self=True):
            loc._archive_single_location()

    def _unarchive_single_location(self):
        """
        Unarchive a single location, caller is expected to handle
        unarchiving children as well.

        This is just used to prevent having to do recursive
        couch queries in `unarchive()`.
        """
        self.is_archived = False
        self.save()

        # reopen supply point case if needed
        sp = self.linked_supply_point()
        # sanity check that the supply point exists and is not open.
        # this is important because if you unarchive a child, then try
        # to unarchive the parent, we don't want to try to open again
        if sp and sp.closed:
            for action in sp.actions:
                if action.action_type == 'close':
                    action.xform.archive(user_id=COMMTRACK_USERNAME)
                    break

    def unarchive(self):
        """
        Unarchive a location and reopen supply point case if it
        exists.
        """
        for loc in self.get_descendants(include_self=True):
            loc._unarchive_single_location()

    def full_delete(self):
        """
        Delete a location and its dependants.
        This also unassigns users assigned to the location.
        """
        to_delete = list(self.get_descendants(include_self=True).couch_locations())
        # if there are errors deleting couch locations, roll back sql delete
        with transaction.atomic():
            self.sql_full_delete()
            Location.get_db().bulk_delete(to_delete)

    def sql_full_delete(self):
        """
        SQL ONLY FULL DELETE
        Delete this location and it's descendants.
        """
        to_delete = self.get_descendants(include_self=True)

        for loc in to_delete:
            loc._sql_close_case_and_remove_users()

        to_delete.delete()

    def _sql_close_case_and_remove_users(self):
        """
        SQL ONLY VERSION
        Closes linked supply point cases for a location and unassigns the users
        assigned to that location.

        Used by both archive and delete methods
        """

        sp = self.linked_supply_point()
        # sanity check that the supply point exists and is still open.
        # this is important because if you archive a child, then try
        # to archive the parent, we don't want to try to close again
        if sp and not sp.closed:
            close_case(sp.case_id, self.domain, COMMTRACK_USERNAME)

        _unassign_users_from_location(self.domain, self.location_id)

    class Meta:
        app_label = 'locations'
        unique_together = ('domain', 'site_code',)

    def __unicode__(self):
        return u"{} ({})".format(self.name, self.domain)

    def __repr__(self):
        return u"SQLLocation(domain='{}', name='{}', location_type='{}')".format(
            self.domain,
            self.name,
            self.location_type.name,
        ).encode('utf-8')

    @property
    def display_name(self):
        return u"{} [{}]".format(self.name, self.location_type.name)

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

    def _make_group_object(self, user_id, case_sharing):
        from corehq.apps.groups.models import UnsavableGroup

        g = UnsavableGroup()
        g.domain = self.domain
        g.users = [user_id] if user_id else []
        g.last_modified = datetime.utcnow()

        if case_sharing:
            g.name = self.get_path_display() + '-Cases'
            g._id = self.location_id
            g.case_sharing = True
            g.reporting = False
        else:
            # reporting groups
            g.name = self.get_path_display()
            g._id = LOCATION_REPORTING_PREFIX + self.location_id
            g.case_sharing = False
            g.reporting = True

        g.metadata = {
            'commcare_location_type': self.location_type.name,
            'commcare_location_name': self.name,
        }
        for key, val in self.metadata.items():
            g.metadata['commcare_location_' + key] = val

        return g

    def get_case_sharing_groups(self, for_user_id=None):
        if self.location_type.shares_cases:
            yield self.case_sharing_group_object(for_user_id)
        if self.location_type.view_descendants:
            for sql_loc in self.get_descendants().filter(location_type__shares_cases=True, is_archived=False):
                yield sql_loc.case_sharing_group_object(for_user_id)

    def case_sharing_group_object(self, user_id=None):
        """
        Returns a fake group object that cannot be saved.

        This is used for giving users access via case
        sharing groups, without having a real group
        for every location that we have to manage/hide.
        """

        return self._make_group_object(
            user_id,
            case_sharing=True,
        )

    @property
    @memoized
    def couch_location(self):
        return Location.get(self.location_id)

    def is_direct_ancestor_of(self, location):
        return (location.get_ancestors(include_self=True)
                .filter(pk=self.pk).exists())

    @classmethod
    def by_domain(cls, domain):
        return cls.objects.filter(domain=domain)

    @property
    def path(self):
        _path = list(reversed(self.lineage))
        _path.append(self._id)
        return _path

    @classmethod
    def by_location_id(cls, location_id):
        try:
            return cls.objects.get(location_id=location_id)
        except cls.DoesNotExist:
            return None

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
        notify_of_deprecation("'sql_location' was just called on a sql_location.  That's kinda silly.")
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


class Location(SyncCouchToSQLMixin, CachedCouchDocumentMixin, Document):
    domain = StringProperty()
    name = StringProperty()
    site_code = StringProperty()  # should be unique, not yet enforced
    # unique id from some external data source
    external_id = StringProperty()
    metadata = DictProperty()
    last_modified = DateTimeProperty()
    is_archived = BooleanProperty(default=False)

    latitude = FloatProperty()
    longitude = FloatProperty()

    @classmethod
    def wrap(cls, data):
        last_modified = data.get('last_modified')
        data.pop('location_type', None)  # Only store location type in SQL
        data.pop('lineage', None)  # Don't try to store lineage
        # if it's missing a Z because of the Aug. 2014 migration
        # that added this in iso_format() without Z, then add a Z
        # (See also Group class)
        from corehq.apps.groups.models import dt_no_Z_re
        if last_modified and dt_no_Z_re.match(last_modified):
            data['last_modified'] += 'Z'
        return super(Location, cls).wrap(data)

    def __init__(self, *args, **kwargs):
        if 'parent' in kwargs:
            # if parent is in the kwargs, this was set from a constructor
            # if parent isn't in kwargs, this was probably pulled from the db
            # and we should look to SQL as source of truth
            parent = kwargs['parent']
            if parent:
                if isinstance(parent, Document):
                    self._sql_parent = parent.sql_location
                else:
                    # 'parent' is a doc id
                    self._sql_parent = SQLLocation.objects.get(location_id=parent)
            else:
                self._sql_parent = None
            del kwargs['parent']

        location_type = kwargs.pop('location_type', None)
        super(Document, self).__init__(*args, **kwargs)
        if location_type:
            self.set_location_type(location_type)

    def __unicode__(self):
        return u"{} ({})".format(self.name, self.domain)

    def __repr__(self):
        return u"Location(domain='{}', name='{}', location_type='{}')".format(
            self.domain,
            self.name,
            self.location_type_name,
        ).encode('utf-8')

    def __eq__(self, other):
        if isinstance(other, Location):
            return self._id == other._id
        else:
            return False

    def __hash__(self):
        return hash(self._id)

    @property
    def sql_location(self):
        return (SQLLocation.objects.prefetch_related('location_type')
                                   .get(location_id=self._id))

    @property
    def location_id(self):
        return self._id

    @property
    def location_type(self):
        notify_of_deprecation(
            "You should use either location_type_name or location_type_object")
        return self.location_type_object.name

    _sql_location_type = None

    @location_type.setter
    def location_type(self, value):
        notify_of_deprecation("You should set location_type using `set_location_type`")
        self.set_location_type(value)

    def set_location_type(self, location_type_name):
        msg = "You can't create a location without a real location type"
        if not location_type_name:
            raise LocationType.DoesNotExist(msg)
        try:
            self._sql_location_type = LocationType.objects.get(
                domain=self.domain,
                name=location_type_name,
            )
        except LocationType.DoesNotExist:
            raise LocationType.DoesNotExist(msg)

    @classmethod
    def _migration_get_fields(cls):
        return ["domain", "name", "site_code", "external_id", "metadata",
                "is_archived", "latitude", "longitude"]

    @classmethod
    def _migration_get_sql_model_class(cls):
        return SQLLocation

    def _migration_do_sync(self):
        sql_location = self._migration_get_or_create_sql_object()

        location_type = self._sql_location_type or sql_location.location_type
        sql_location.location_type = location_type
        # sync parent connection
        if hasattr(self, '_sql_parent'):
            sql_location.parent = self._sql_parent

        self._migration_sync_to_sql(sql_location)

    def save(self, *args, **kwargs):
        self.last_modified = datetime.utcnow()

        # lazy migration for site_code
        if not self.site_code:
            from corehq.apps.commtrack.util import generate_code
            all_codes = [
                code.lower() for code in
                (SQLLocation.objects.filter(domain=self.domain)
                                    .values_list('site_code', flat=True))
            ]
            self.site_code = generate_code(self.name, all_codes)

        # Set the UUID here so we can save to SQL first (easier to rollback)
        if not self._id:
            self._id = self.get_db().server.next_uuid()

        sync_to_sql = kwargs.pop('sync_to_sql', True)
        kwargs['sync_to_sql'] = False  # only sync here
        with transaction.atomic():
            if sync_to_sql:
                self._migration_do_sync()
            super(Location, self).save(*args, **kwargs)

    @classmethod
    def filter_by_type(cls, domain, loc_type, root_loc=None):
        if root_loc:
            query = root_loc.sql_location.get_descendants(include_self=True)
        else:
            query = SQLLocation.objects
        ids = (query.filter(domain=domain, location_type__name=loc_type)
                    .location_ids())

        return (
            cls.wrap(l) for l in iter_docs(cls.get_db(), list(ids))
            if not l.get('is_archived', False)
        )

    @classmethod
    def by_domain(cls, domain, include_docs=True):
        relevant_ids = SQLLocation.objects.filter(domain=domain).location_ids()
        if not include_docs:
            return relevant_ids
        else:
            return (
                cls.wrap(l) for l in iter_docs(cls.get_db(), list(relevant_ids))
                if not l.get('is_archived', False)
            )

    @classmethod
    def by_site_code(cls, domain, site_code):
        """
        This method directly looks up a single location
        and can return archived locations.
        """
        try:
            return (SQLLocation.objects.get(domain=domain,
                                            site_code__iexact=site_code)
                    .couch_location)
        except (SQLLocation.DoesNotExist, ResourceNotFound):
            return None

    @classmethod
    def root_locations(cls, domain):
        """
        Return all active top level locations for this domain
        """
        return list(SQLLocation.root_locations(domain).couch_locations())

    @property
    def parent_location_id(self):
        return self.parent.location_id if self.parent else None

    @property
    def parent_id(self):
        # TODO this is deprecated as of 2016-07-19
        # delete after we're sure this isn't called dynamically
        # Django automagically reserves field_name+_id for foreign key fields,
        # so because we have SQLLocation.parent, SQLLocation.parent_id refers
        # to the Django primary key
        notify_of_deprecation("parent_id should be replaced by parent_location_id")
        return self.parent_location_id

    @property
    def parent(self):
        if hasattr(self, '_sql_parent'):
            return self._sql_parent.couch_location if self._sql_parent else None
        else:
            return self.sql_location.parent.couch_location if self.sql_location.parent else None

    @property
    def lineage(self):
        return self.sql_location.lineage

    @property
    def path(self):
        return self.sql_location.path

    @property
    def descendants(self):
        """return list of all locations that have this location as an ancestor"""
        return list(self.sql_location.get_descendants().couch_locations())

    def get_children(self):
        """return list of immediate children of this location"""
        return self.sql_location.get_children().couch_locations()

    def linked_supply_point(self):
        return self.sql_location.linked_supply_point()

    @property
    def group_id(self):
        """
        This just returns the location's id. It used to add
        a prefix.
        """
        return self.location_id

    @property
    def location_type_object(self):
        return self._sql_location_type or self.sql_location.location_type

    @property
    def location_type_name(self):
        return self.location_type_object.name


class LocationFixtureConfiguration(models.Model):
    domain = models.CharField(primary_key=True, max_length=255)
    sync_flat_fixture = models.BooleanField(default=True)
    sync_hierarchical_fixture = models.BooleanField(default=True)

    def __repr__(self):
        return u'{}: flat: {}, hierarchical: {}'.format(
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
    from corehq.apps.locations.dbaccessors import get_all_users_by_location
    for user in get_all_users_by_location(domain, location_id):
        if user.is_web_user():
            user.unset_location_by_id(domain, location_id, fall_back_to_next=True)
        elif user.is_commcare_user():
            user.unset_location_by_id(location_id, fall_back_to_next=True)
