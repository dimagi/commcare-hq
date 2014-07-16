from couchdbkit import ResourceNotFound
from couchdbkit.ext.django.schema import *
import itertools
from corehq.apps.cachehq.mixins import CachedCouchDocumentMixin
from dimagi.utils.couch.database import get_db, iter_docs
from django import forms
from django.core.urlresolvers import reverse

class Location(CachedCouchDocumentMixin, Document):
    domain = StringProperty()
    name = StringProperty()
    location_type = StringProperty()
    site_code = StringProperty() # should be unique, not yet enforced
    # unique id from some external data source
    external_id = StringProperty()
    metadata = DictProperty()

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

    @classmethod
    def filter_by_type(cls, domain, loc_type, root_loc=None):
        loc_id = root_loc._id if root_loc else None
        relevant_ids = [r['id'] for r in cls.get_db().view('locations/by_type',
            reduce=False,
            startkey=[domain, loc_type, loc_id],
            endkey=[domain, loc_type, loc_id, {}],
        ).all()]
        return (cls.wrap(l) for l in iter_docs(cls.get_db(), list(relevant_ids)))

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
        relevant_ids = set([r['id'] for r in cls.get_db().view('locations/by_type',
            reduce=False,
            startkey=[domain],
            endkey=[domain, {}],
        ).all()])
        return (cls.wrap(l) for l in iter_docs(cls.get_db(), list(relevant_ids)))

    @classmethod
    def root_locations(cls, domain):
        return root_locations(domain)

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

    def linked_docs(self, doc_type, include_descendants=False):
        startkey = [self.domain, self._id, doc_type]
        if not include_descendants:
            startkey.append(True)
        endkey = list(startkey)
        endkey.append({})
        # returns arbitrary doc types, so can't call self.view()
        return [k['doc'] for k in get_db().view('locations/linked_docs', startkey=startkey, endkey=endkey, include_docs=True)]

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
    return [Location.get(id) for id in ids]

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
