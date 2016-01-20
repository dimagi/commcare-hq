import warnings
from functools import partial
from couchdbkit import ResourceNotFound
from dimagi.ext.couchdbkit import *
import itertools
from corehq.apps.cachehq.mixins import CachedCouchDocumentMixin
from dimagi.utils.couch.database import iter_docs
from dimagi.utils.decorators.memoized import memoized
from datetime import datetime
from django.db import models, transaction
import json_field
from casexml.apps.case.cleanup import close_case
from corehq.apps.commtrack.const import COMMTRACK_USERNAME
from corehq.apps.domain.models import Domain
from corehq.apps.products.models import SQLProduct
from corehq.toggles import LOCATION_TYPE_STOCK_RATES
from mptt.models import MPTTModel, TreeForeignKey, TreeManager


LOCATION_REPORTING_PREFIX = 'locationreportinggroup-'


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


class LocationType(models.Model):
    domain = models.CharField(max_length=255, db_index=True)
    name = models.CharField(max_length=255)
    code = models.SlugField(db_index=False, null=True)
    parent_type = models.ForeignKey('self', null=True)
    administrative = models.BooleanField(default=False)
    shares_cases = models.BooleanField(default=False)
    view_descendants = models.BooleanField(default=False)
    last_modified = models.DateTimeField(auto_now=True)

    emergency_level = StockLevelField(default=0.5)
    understock_threshold = StockLevelField(default=1.5)
    overstock_threshold = StockLevelField(default=3.0)

    objects = LocationTypeManager()

    class Meta:
        app_label = 'locations'

    def _populate_stock_levels(self):
        from corehq.apps.commtrack.models import CommtrackConfig
        ct_config = CommtrackConfig.for_domain(self.domain)
        if (
            (ct_config is None)
            or (not Domain.get_by_name(self.domain).commtrack_enabled)
            or LOCATION_TYPE_STOCK_RATES.enabled(self.domain)
        ):
            return
        config = ct_config.stock_levels_config
        self.emergency_level = config.emergency_level
        self.understock_threshold = config.understock_threshold
        self.overstock_threshold = config.overstock_threshold

    def save(self, *args, **kwargs):
        if not self.code:
            from corehq.apps.commtrack.util import unicode_slug
            self.code = unicode_slug(self.name)
        self._populate_stock_levels()
        return super(LocationType, self).save(*args, **kwargs)

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


class LocationQuerySet(LocationQueriesMixin, models.query.QuerySet):
    pass


class LocationManager(LocationQueriesMixin, TreeManager):
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


class OnlyUnarchivedLocationManager(LocationManager):
    def get_queryset(self):
        return (super(OnlyUnarchivedLocationManager, self).get_query_set()
                .filter(is_archived=False))


class SQLLocation(MPTTModel):
    domain = models.CharField(max_length=255, db_index=True)
    name = models.CharField(max_length=100, null=True)
    location_id = models.CharField(max_length=100, db_index=True, unique=True)
    location_type = models.ForeignKey(LocationType)
    site_code = models.CharField(max_length=255)
    external_id = models.CharField(max_length=255, null=True)
    metadata = json_field.JSONField(default={})
    created_at = models.DateTimeField(auto_now_add=True)
    last_modified = models.DateTimeField(auto_now=True)
    is_archived = models.BooleanField(default=False)
    latitude = models.DecimalField(max_digits=20, decimal_places=10, null=True)
    longitude = models.DecimalField(max_digits=20, decimal_places=10, null=True)
    parent = TreeForeignKey('self', null=True, blank=True, related_name='children')

    # Use getter and setter below to access this value
    # since stocks_all_products can cause an empty list to
    # be what is stored for a location that actually has
    # all products available.
    _products = models.ManyToManyField(SQLProduct, null=True)
    stocks_all_products = models.BooleanField(default=True)

    supply_point_id = models.CharField(max_length=255, db_index=True, unique=True, null=True)

    objects = LocationManager()
    # This should really be the default location manager
    active_objects = OnlyUnarchivedLocationManager()

    @property
    def get_id(self):
        return self.location_id

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
        return _filter_for_archived(children, include_archive_ancestors)

    @classmethod
    def root_locations(cls, domain, include_archive_ancestors=False):
        roots = cls.objects.root_nodes().filter(domain=domain)
        return _filter_for_archived(roots, include_archive_ancestors)

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

    def reporting_group_object(self, user_id=None):
        """
        Returns a fake group object that cannot be saved.

        Similar to case_sharing_group_object method, but for
        reporting groups.
        """

        return self._make_group_object(
            user_id,
            case_sharing=False,
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
        # This exists for backwards compatability with couch locations
        return list(self.get_ancestors(include_self=True)
                    .values_list('location_id', flat=True))

    @classmethod
    def by_location_id(cls, location_id):
        try:
            return cls.objects.get(location_id=location_id)
        except cls.DoesNotExist:
            return None


def _filter_for_archived(locations, include_archive_ancestors):
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


class Location(CachedCouchDocumentMixin, Document):
    domain = StringProperty()
    name = StringProperty()
    site_code = StringProperty() # should be unique, not yet enforced
    # unique id from some external data source
    external_id = StringProperty()
    metadata = DictProperty()
    last_modified = DateTimeProperty()
    is_archived = BooleanProperty(default=False)

    latitude = FloatProperty()
    longitude = FloatProperty()

    # a list of doc ids, referring to the parent location, then the
    # grand-parent, and so on up to the root location in the hierarchy
    # TODO: in future, support multiple types of parentage with
    # independent hierarchies
    lineage = StringListProperty()
    previous_parents = StringListProperty()

    @classmethod
    def wrap(cls, data):
        last_modified = data.get('last_modified')
        data.pop('location_type', None)  # Only store location type in SQL
        # if it's missing a Z because of the Aug. 2014 migration
        # that added this in iso_format() without Z, then add a Z
        # (See also Group class)
        from corehq.apps.groups.models import dt_no_Z_re
        if last_modified and dt_no_Z_re.match(last_modified):
            data['last_modified'] += 'Z'
        return super(Location, cls).wrap(data)

    def __init__(self, *args, **kwargs):
        from corehq.apps.locations.util import get_lineage_from_location, get_lineage_from_location_id
        if 'parent' in kwargs:
            parent = kwargs['parent']
            if parent:
                if isinstance(parent, Document):
                    lineage = get_lineage_from_location(parent)
                else:
                    # 'parent' is a doc id
                    lineage = get_lineage_from_location_id(parent)
            else:
                lineage = []
            kwargs['lineage'] = lineage
            del kwargs['parent']

        location_type = kwargs.pop('location_type', None)
        super(Document, self).__init__(*args, **kwargs)
        if location_type:
            self.location_type = location_type

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

    def _sync_location(self):
        """
        This method returns an unsaved SQLLocation object, as it lets
        us more easily handle the bulk syncing of data in tasks and
        lets us only save the SQLLocation if the Location was successfuly
        saved. The actual saving is done in the Location save method.
        """

        properties_to_sync = [
            ('location_id', '_id'),
            'domain',
            'name',
            'site_code',
            'external_id',
            'latitude',
            'longitude',
            'is_archived',
            'metadata'
        ]

        try:
            sql_location = SQLLocation.objects.get(location_id=self._id)
        except SQLLocation.DoesNotExist:
            sql_location = SQLLocation(
                domain=self.domain,
            )

        # One of these will fail if you try to save a location without a type
        location_type = self._sql_location_type or sql_location.location_type
        sql_location.location_type = location_type

        for prop in properties_to_sync:
            if isinstance(prop, tuple):
                sql_prop, couch_prop = prop
            else:
                sql_prop = couch_prop = prop

            if hasattr(self, couch_prop):
                setattr(sql_location, sql_prop, getattr(self, couch_prop))

        # sync supply point id
        sp = self.linked_supply_point()
        if sp:
            sql_location.supply_point_id = sp.case_id

        # sync parent connection
        parent_id = self.parent_id
        if parent_id:
            sql_location.parent = SQLLocation.objects.get(location_id=parent_id)
        else:
            sql_location.parent = None
        return sql_location

    @property
    def sql_location(self):
        return (SQLLocation.objects.prefetch_related('location_type')
                                   .get(location_id=self._id))

    @property
    def location_type(self):
        return self.location_type_object.name

    @property
    def location_id(self):
        return self._id

    _sql_location_type = None
    @location_type.setter
    def location_type(self, value):
        msg = "You can't create a location without a real location type"
        if not value:
            raise LocationType.DoesNotExist(msg)
        try:
            self._sql_location_type = LocationType.objects.get(
                domain=self.domain,
                name=value,
            )
        except LocationType.DoesNotExist:
            raise LocationType.DoesNotExist(msg)

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
        Mark a location and its dependants as archived.
        This will cause it (and its data) to not show up in default Couch and
        SQL views.  This also unassigns users assigned to the location.
        """
        for loc in [self] + self.descendants:
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
        for loc in [self] + self.descendants:
            loc._unarchive_single_location()

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

        _unassign_users_from_location(self.domain, self._id)

    def full_delete(self):
        """
        Delete a location and its dependants.
        This also unassigns users assigned to the location.
        """
        to_delete = [self] + self.descendants

        # if there are errors deleting couch locations, roll back sql delete
        with transaction.atomic():
            SQLLocation.objects.get(location_id=self._id).delete()
            for loc in to_delete:
                loc._close_case_and_remove_users()
            Location.get_db().bulk_delete(to_delete)

    def save(self, *args, **kwargs):
        """
        Saving a couch version of Location will trigger
        one way syncing to the SQLLocation version of this
        location.
        """
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

        sql_location = None
        result = super(Location, self).save(*args, **kwargs)

        # try sync locations and when SQLLocation doesn't returned, removed Couch object from database.
        # added because when we sync location by tasks we can have behavior that the task can be
        # killed in _sync_location method and this causes the problems
        try:
            sql_location = self._sync_location()
        finally:
            if sql_location:
                sql_location.save()
            else:
                self.delete()
                result = None

        return result

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
        except SQLLocation.DoesNotExist:
            return None

    @classmethod
    def root_locations(cls, domain):
        """
        Return all active top level locations for this domain
        """
        return list(SQLLocation.root_locations(domain).couch_locations())

    @classmethod
    def get_in_domain(cls, domain, id):
        if id:
            try:
                loc = Location.get(id)
                assert domain == loc.domain
                return loc
            except (ResourceNotFound, AssertionError):
                pass
        return None

    @property
    def is_root(self):
        return not self.lineage

    @property
    def parent_id(self):
        if self.is_root:
            return None
        return self.lineage[0]

    @property
    def parent(self):
        parent_id = self.parent_id
        return Location.get(parent_id) if parent_id else None

    def siblings(self, parent=None):
        if not parent:
            parent = self.parent
        locs = (parent.children if parent else self.root_locations(self.domain))
        return [loc for loc in locs if loc.location_id != self._id]

    @property
    def path(self):
        _path = list(reversed(self.lineage))
        _path.append(self._id)
        return _path

    @property
    def descendants(self):
        """return list of all locations that have this location as an ancestor"""
        return list(self.sql_location.get_descendants().couch_locations())

    @property
    def children(self):
        """return list of immediate children of this location"""
        return list(SQLLocation.objects.filter(parent=self.sql_location)
                                       .couch_locations())

    def linked_supply_point(self):
        from corehq.apps.commtrack.dbaccessors import get_supply_point_case_by_location
        return get_supply_point_case_by_location(self)

    @property
    def group_id(self):
        """
        This just returns the location's id. It used to add
        a prefix.
        """
        return self._id

    @property
    def location_type_object(self):
        return self._sql_location_type or self.sql_location.location_type

    @property
    def location_type_name(self):
        return self.location_type_object.name



def _unassign_users_from_location(domain, location_id):
    """
    Unset location for all users assigned to that location.
    """
    from corehq.apps.locations.dbaccessors import get_all_users_by_location
    for user in get_all_users_by_location(domain, location_id):
        if user.is_web_user():
            user.unset_location(domain)
        elif user.is_commcare_user():
            user.unset_location()
