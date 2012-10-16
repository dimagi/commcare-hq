from couchdbkit.ext.django.schema import *
import itertools

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
        start_key = list(itertools.chain([self.domain], self.path, ['']))
        end_key = list(itertools.chain(start_key[:-1], [{}]))
        return start_key, end_key

    @property
    def descendants(self):
        """return list of all locations that have this location as an ancestor"""
        start_key, end_key = self._key_bounds
        return self.view('locations/hierarchy', start_key=start_key, end_key=end_key, reduce=False, include_docs=True).all()

    @property
    def children(self):
        """return list of immediate children of this location"""
        start_key, end_key = self._key_bounds
        depth = len(self.path) + 2 # 1 for domain, 1 for next location level
        q = self.view('locations/hierarchy', start_key=start_key, end_key=end_key, group_level=depth)
        keys = [e['key'] for e in q if len(e['key']) == depth]
        return self.view('locations/hierarchy', keys=keys, reduce=False, include_docs=True).all()
