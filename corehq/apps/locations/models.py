from functools import partial
from couchdbkit import ResourceNotFound
from couchdbkit.ext.django.schema import *
import itertools
from corehq.apps.cachehq.mixins import CachedCouchDocumentMixin
from corehq.ext.couchdbkit import USecDateTimeProperty
from dimagi.utils.couch.database import iter_docs
from dimagi.utils.decorators.memoized import memoized
from datetime import datetime
from django.db import models
import json_field
from casexml.apps.case.cleanup import close_case
from corehq.apps.commtrack.const import COMMTRACK_USERNAME
from corehq.apps.domain.models import Domain
from corehq.apps.products.models import SQLProduct
from corehq.toggles import LOCATION_TYPE_STOCK_RATES
from mptt.models import MPTTModel, TreeForeignKey


LOCATION_SHARING_PREFIX = 'locationgroup-'
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

    emergency_level = StockLevelField(default=0.5)
    understock_threshold = StockLevelField(default=1.5)
    overstock_threshold = StockLevelField(default=3.0)

    objects = LocationTypeManager()

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


class SQLLocation(MPTTModel):
    domain = models.CharField(max_length=255, db_index=True)
    name = models.CharField(max_length=100, null=True)
    location_id = models.CharField(max_length=100, db_index=True, unique=True)
    location_type = models.ForeignKey(LocationType, null=True)
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
        unique_together = ('domain', 'site_code',)

    def __unicode__(self):
        return u"{} ({})".format(self.name, self.domain)

    def __repr__(self):
        return "<SQLLocation(domain=%s, name=%s)>" % (
            self.domain,
            self.name
        )

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

    def _make_group_object(self, user_id, case_sharing):
        def group_name():
            return '/'.join(
                list(self.get_ancestors().values_list('name', flat=True)) +
                [self.name]
            )

        from corehq.apps.groups.models import UnsavableGroup

        g = UnsavableGroup()
        g.domain = self.domain
        g.users = [user_id] if user_id else []
        g.last_modified = datetime.utcnow()

        if case_sharing:
            g.name = group_name() + '-Cases'
            g._id = LOCATION_SHARING_PREFIX + self.location_id
            g.case_sharing = True
            g.reporting = False
        else:
            # reporting groups
            g.name = group_name()
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

    def case_sharing_group_object(self, user_id=None):
        """
        Returns a fake group object that cannot be saved.

        This is used for giving users access via case
        sharing groups, without having a real group
        for every location that we have to manage/hide.
        """

        return self._make_group_object(
            user_id,
            True,
        )

    def reporting_group_object(self, user_id=None):
        """
        Returns a fake group object that cannot be saved.

        Similar to case_sharing_group_object method, but for
        reporting groups.
        """

        return self._make_group_object(
            user_id,
            False,
        )

    @property
    @memoized
    def couch_location(self):
        return Location.get(self.location_id)


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
    location_type = StringProperty()
    site_code = StringProperty() # should be unique, not yet enforced
    # unique id from some external data source
    external_id = StringProperty()
    metadata = DictProperty()
    last_modified = USecDateTimeProperty()
    is_archived = BooleanProperty(default=False)

    latitude = FloatProperty()
    longitude = FloatProperty()

    # a list of doc ids, referring to the parent location, then the
    # grand-parent, and so on up to the root location in the hierarchy
    # TODO: in future, support multiple types of parentage with
    # independent hierarchies
    lineage = StringListProperty()
    previous_parents = StringListProperty()

    def __init__(self, *args, **kwargs):
        if 'parent' in kwargs:
            parent = kwargs['parent']
            if parent:
                if not isinstance(parent, Document):
                    # 'parent' is a doc id
                    parent = Location.get(parent)
                lineage = list(reversed(parent.path))
            else:
                lineage = []
            kwargs['lineage'] = lineage
            del kwargs['parent']

        super(Document, self).__init__(*args, **kwargs)

    def __repr__(self):
        return "%s (%s)" % (self.name, self.location_type)

    def __eq__(self, other):
        if isinstance(other, Location):
            return self._id == other._id
        else:
            return False

    def __hash__(self):
        return hash(self._id)

    def _sync_location(self):
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

        sql_location, is_new = SQLLocation.objects.get_or_create(
            location_id=self._id,
            defaults={
                'domain': self.domain,
                'site_code': self.site_code
            }
        )

        if is_new or (sql_location.location_type.name != self.location_type):
            sql_location.location_type, _ = LocationType.objects.get_or_create(
                domain=self.domain,
                name=self.location_type,
            )

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
            sql_location.supply_point_id = sp._id

        # sync parent connection
        parent_id = self.parent_id
        if parent_id:
            sql_location.parent = SQLLocation.objects.get(location_id=parent_id)

        sql_location.save()

    @property
    def sql_location(self):
        return SQLLocation.objects.get(location_id=self._id)

    def _archive_single_location(self):
        """
        Archive a single location, caller is expected to handle
        archiving children as well.

        This is just used to prevent having to do recursive
        couch queries in `archive()`.
        """
        self.is_archived = True
        self.save()

        sp = self.linked_supply_point()
        # sanity check that the supply point exists and is still open.
        # this is important because if you archive a child, then try
        # to archive the parent, we don't want to try to close again
        if sp and not sp.closed:
            close_case(sp._id, self.domain, COMMTRACK_USERNAME)

    def archive(self):
        """
        Mark a location and its dependants as archived.
        This will cause it (and its data) to not show up in default
        Couch and SQL views.
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
                    action.xform.archive(user=COMMTRACK_USERNAME)
                    break

    def unarchive(self):
        """
        Unarchive a location and reopen supply point case if it
        exists.
        """
        for loc in [self] + self.descendants:
            loc._unarchive_single_location()

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
            self.site_code = generate_code(
                self.name,
                Location.site_codes_for_domain(self.domain)
            )

        result = super(Location, self).save(*args, **kwargs)

        self._sync_location()

        return result

    @classmethod
    def filter_by_type(cls, domain, loc_type, root_loc=None):
        loc_id = root_loc._id if root_loc else None
        relevant_ids = [r['id'] for r in cls.get_db().view('locations/by_type',
            reduce=False,
            startkey=[domain, loc_type, loc_id],
            endkey=[domain, loc_type, loc_id, {}],
        ).all()]
        return (
            cls.wrap(l) for l in iter_docs(cls.get_db(), list(relevant_ids))
            if not l.get('is_archived', False)
        )

    @classmethod
    def filter_by_type_count(cls, domain, loc_type, root_loc=None):
        loc_id = root_loc._id if root_loc else None
        return cls.get_db().view('locations/by_type',
            reduce=True,
            startkey=[domain, loc_type, loc_id],
            endkey=[domain, loc_type, loc_id, {}],
        ).one()['value']

    @classmethod
    def by_domain(cls, domain, include_docs=True):
        relevant_ids = set([r['id'] for r in cls.get_db().view(
            'locations/by_type',
            reduce=False,
            startkey=[domain],
            endkey=[domain, {}],
        ).all()])

        if not include_docs:
            return relevant_ids
        else:
            return (
                cls.wrap(l) for l in iter_docs(cls.get_db(), list(relevant_ids))
                if not l.get('is_archived', False)
            )

    @classmethod
    def site_codes_for_domain(cls, domain):
        """
        This method is only used in management commands and lazy
        migrations so DOES NOT exclude archived locations.
        """
        return set([r['key'][1] for r in cls.get_db().view(
            'locations/prop_index_site_code',
            reduce=False,
            startkey=[domain],
            endkey=[domain, {}],
        ).all()])

    @classmethod
    def by_site_code(cls, domain, site_code):
        """
        This method directly looks up a single location
        and can return archived locations.
        """
        result = cls.get_db().view(
            'locations/prop_index_site_code',
            reduce=False,
            startkey=[domain, site_code],
            endkey=[domain, site_code, {}],
        ).first()
        return Location.get(result['id']) if result else None

    @classmethod
    def root_locations(cls, domain):
        """
        Return all active top level locations for this domain
        """
        return root_locations(domain)

    @classmethod
    def all_locations(cls, domain):
        return all_locations(domain)

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
        return [loc for loc in (parent.children if parent else root_locations(self.domain)) if loc._id != self._id]

    @property
    def path(self):
        _path = list(reversed(self.lineage))
        _path.append(self._id)
        return _path

    @property
    def _key_bounds(self):
        startkey = list(itertools.chain([self.domain], self.path, ['']))
        endkey = list(itertools.chain(startkey[:-1], [{}]))
        return startkey, endkey

    @property
    def descendants(self):
        """return list of all locations that have this location as an ancestor"""
        startkey, endkey = self._key_bounds
        return self.view('locations/hierarchy', startkey=startkey, endkey=endkey, reduce=False, include_docs=True).all()

    @property
    def children(self):
        """return list of immediate children of this location"""
        startkey, endkey = self._key_bounds
        depth = len(self.path) + 2  # 1 for domain, 1 for next location level
        q = self.view('locations/hierarchy', startkey=startkey, endkey=endkey, group_level=depth)
        keys = [e['key'] for e in q if len(e['key']) == depth]
        return self.view('locations/hierarchy', keys=keys, reduce=False, include_docs=True).all()

    @property
    def _geopoint(self):
        return '%s %s' % (self.latitude, self.longitude) if self.latitude is not None and self.longitude is not None else None

    def linked_supply_point(self):
        from corehq.apps.commtrack.models import SupplyPointCase
        return SupplyPointCase.get_by_location(self)

    @property
    def group_id(self):
        """
        Returns the id with a prefix because this is
        the magic id we are force setting the locations
        case sharing group to be.

        This is also the id that owns supply point cases.
        """
        return LOCATION_SHARING_PREFIX + self._id

    @property
    def location_type_object(self):
        return self.sql_location.location_type


def root_locations(domain):
    results = Location.get_db().view('locations/hierarchy',
                                     startkey=[domain], endkey=[domain, {}],
                                     reduce=True, group_level=2)

    ids = [res['key'][-1] for res in results]
    locs = [Location.get(id) for id in ids]
    return [loc for loc in locs if not loc.is_archived]


def all_locations(domain):
    return Location.view('locations/hierarchy', startkey=[domain], endkey=[domain, {}],
                         reduce=False, include_docs=True).all()
