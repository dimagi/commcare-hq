from couchdbkit.ext.django.schema import *
import itertools
from dimagi.utils.couch.database import get_db

class Location(Document):
    domain = StringProperty()
    name = StringProperty()
    location_type = StringProperty()

    # a list of doc ids, referring to the parent location, then the
    # grand-parent, and so on up to the root location in the hierarchy
    # TODO: in future, support multiple types of parentage with
    # independent hierarchies
    lineage = StringListProperty()

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
    locs = Location.view('locations/hierarchy', startkey=[domain], endkey=[domain, {}], reduce=False, include_docs=True).all()
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
    
