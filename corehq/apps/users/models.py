from couchdbkit.ext.django.schema import Document
from couchdbkit.schema.properties import ListProperty, StringProperty

class DagError(Exception):
    pass

class DagConf(Document):
    roles = ListProperty()

class DagNode(Document):
    child_ids = ListProperty()
    conf_id = StringProperty()
    role = StringProperty()
    _roles = None
    @property
    def roles(self):
        if not self._roles:
            self._roles = DagConf.get(self.conf_id).roles
        return self._roles

    def add(self, child):
        if self.roles.index(child.role) <= self.roles.index(self.role):
            raise DagError
        if child not in self.child_ids:
            self.child_ids.append(child._id)
            self.save()

    @property
    def parents(self):
        return DagNode.view('users/parents', key=self._id).all()

    def remove(self, child):
        delete = False
        if len(child.parents) == 1:
            if child.child_ids:
                raise DagError
            else:
                delete = True
        if child._id in self.child_ids:
            self.child_ids.remove(child._id)
            self.save()
        if delete:
            child.delete()