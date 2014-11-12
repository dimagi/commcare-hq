from couchdbkit import ResourceNotFound
from couchdbkit.ext.django.schema import *
import itertools
from corehq.apps.cachehq.mixins import CachedCouchDocumentMixin
from dimagi.utils.couch.database import get_db, iter_docs
from django import forms
from django.core.urlresolvers import reverse
from datetime import datetime
from django.db import models
import json_field
from casexml.apps.case.cleanup import close_case
from corehq.apps.commtrack.const import COMMTRACK_USERNAME
from mptt.models import MPTTModel, TreeForeignKey


class SQLLocation(MPTTModel):
    domain = models.CharField(max_length=255, db_index=True)
    name = models.CharField(max_length=100, null=True)
    location_id = models.CharField(max_length=100, db_index=True, unique=True)
    location_type = models.CharField(max_length=255)
    site_code = models.CharField(max_length=255)
    external_id = models.CharField(max_length=255, null=True)
    metadata = json_field.JSONField(default={})
    created_at = models.DateTimeField(auto_now_add=True)
    last_modified = models.DateTimeField(auto_now=True)
    is_archived = models.BooleanField(default=False)
    latitude = models.DecimalField(max_digits=20, decimal_places=10, null=True)
    longitude = models.DecimalField(max_digits=20, decimal_places=10, null=True)
    parent = TreeForeignKey('self', null=True, blank=True, related_name='children')

    supply_point_id = models.CharField(max_length=255, db_index=True, unique=True, null=True)

    class Meta:
        unique_together = ('domain', 'site_code',)

    def __repr__(self):
        return "<SQLLocation(domain=%s, name=%s)>" % (
            self.domain,
            self.name
        )

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

    def _sync_location(self):
        properties_to_sync = [
            ('location_id', '_id'),
            'domain',
            'name',
            'location_type',
            'site_code',
            'external_id',
            'latitude',
            'longitude',
            'is_archived',
        ]

        sql_location, _ = SQLLocation.objects.get_or_create(
            location_id=self._id,
            defaults={
                'domain': self.domain,
                'site_code': self.site_code
            }
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
        self.last_modified = datetime.now()

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
    def by_domain(cls, domain):
        relevant_ids = set([r['id'] for r in cls.get_db().view(
            'locations/by_type',
            reduce=False,
            startkey=[domain],
            endkey=[domain, {}],
        ).all()])
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


class CustomProperty(Document):
    name = StringProperty()
    datatype = StringProperty()
    label = StringProperty()
    required = BooleanProperty()
    help_text = StringProperty()
    unique = StringProperty()

    def field_type(self):
        return getattr(forms, '%sField' % (self.datatype or 'Char'))

    def field(self, initial=None):
        kwargs = dict(
            label=self.label,
            required=(self.required if self.required is not None else False),
            help_text=self.help_text,
            initial=initial,
        )

        choices = getattr(self, 'choices', None)
        if choices:
            if choices['mode'] == 'static':
                def mk_choice(spec):
                    return spec if hasattr(spec, '__iter__') else (spec, spec)
                choices = [mk_choice(c) for c in choices['args']]
            elif choices['mode'] == 'fixture':
                raise RuntimeError('choices from fixture not supported yet')
            else:
                raise ValueError('unknown choices mode [%s]' % choices['mode'])
            kwargs['choices'] = choices

        return self.field_type()(**kwargs)

    def custom_validate(self, loc, val, prop_name):
        if self.unique:
            self.validate_uniqueness(loc, val, prop_name)

    def validate_uniqueness(self, loc, val, prop_name):
        def normalize(val):
            try:
                return val.lower() # case-insensitive comparison
            except AttributeError:
                return val
        val = normalize(val)

        from corehq.apps.locations.util import property_uniqueness
        conflict_ids = property_uniqueness(loc.domain, loc, prop_name, val, self.unique)

        if conflict_ids:
            conflict_loc = Location.get(conflict_ids.pop())
            raise ValueError('value must be unique; conflicts with <a href="%s">%s %s</a>' %
                             (reverse('edit_location', kwargs={'domain': loc.domain, 'loc_id': conflict_loc._id}),
                              conflict_loc.name, conflict_loc.location_type))
