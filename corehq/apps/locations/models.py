from couchdbkit.ext.django.schema import *
import itertools
from dimagi.utils.couch.database import get_db
from django import forms
from django.core.urlresolvers import reverse

class Location(Document):
    domain = StringProperty()
    name = StringProperty()
    location_type = StringProperty()

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
        return cls.view('locations/by_type',
                        startkey=[domain, loc_type, loc_id],
                        endkey=[domain, loc_type, loc_id, {}],
                        include_docs=True).all()

    @property
    def is_root(self):
        return not self.lineage

    @property
    def parent(self):
        if self.is_root:
            return None
        else:
            return Location.get(self.lineage[0])

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
        depth = len(self.path) + 2 # 1 for domain, 1 for next location level
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

def location_tree(domain):
    """build a hierarchical tree of the entire location structure for a domain"""
    # this is going to be extremely slow as the number of locations gets big
    locs = all_locations(domain)
    locs.sort(key=lambda l: l.path) # parents must appear before their children; couch should
    # return docs in the correct order, but, just to be safe...
    locs_by_id = dict((l._id, l) for l in locs)

    tree_root = []
    for loc in locs:
        loc._children = []

        try:
            parent_id = loc.lineage[0]
        except IndexError:
            parent_id = None

        if parent_id:
            parent_loc = locs_by_id[parent_id]
            parent_loc._children.append(loc)
        else:
            tree_root.append(loc)
    return tree_root
    
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
        self.validate_uniqueness(loc, val, prop_name)

    def validate_uniqueness(self, loc, val, prop_name):
        def normalize(val):
            try:
                return val.lower() # case-insensitive comparison
            except AttributeError:
                return val
        val = normalize(val)

        uniqueness_set = []
        if self.unique == 'global':
            uniqueness_set = [l for l in all_locations(loc.domain) if l._id != loc._id]
        elif self.unique == 'siblings':
            uniqueness_set = loc.siblings()

        unique_conflict = [l for l in uniqueness_set if val == normalize(getattr(l, prop_name, None))]
        if unique_conflict:
            conflict_loc = unique_conflict[0]
            raise ValueError('value must be unique; conflicts with <a href="%s">%s %s</a>' %
                             (reverse('edit_location', kwargs={'domain': loc.domain, 'loc_id': conflict_loc._id}),
                              conflict_loc.name, conflict_loc.location_type))
