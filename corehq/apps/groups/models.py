from __future__ import absolute_import
from functools import partial
from couchdbkit.ext.django.schema import *
from dimagi.utils.decorators.memoized import memoized
from corehq.apps.users.models import CouchUser, CommCareUser
from dimagi.utils.couch.undo import UndoableDocument, DeleteDocRecord
from django.conf import settings


class Group(UndoableDocument):
    """
    The main use case for these 'groups' of users is currently
    so that we can break down reports by arbitrary regions.
    
    (Things like who sees what reports are determined by permissions.) 
    """
    domain = StringProperty()
    name = StringProperty()
    # a list of user ids for users
    users = ListProperty()
    path = ListProperty()
    case_sharing = BooleanProperty()
    reporting = BooleanProperty(default=True)

    # custom data can live here
    metadata = DictProperty()

    def add_user(self, couch_user_id, save=True):
        if not isinstance(couch_user_id, basestring):
            couch_user_id = couch_user_id.user_id
        if couch_user_id not in self.users:
            self.users.append(couch_user_id)
        if save:
            self.save()
        
    def remove_user(self, couch_user_id, save=True):
        if not isinstance(couch_user_id, basestring):
            couch_user_id = couch_user_id.user_id
        if couch_user_id in self.users:
            for i in range(0,len(self.users)):
                if self.users[i] == couch_user_id:
                    del self.users[i]
                    if save:
                        self.save()
                    return
    
    def add_group(self, group):
        group.add_to_group(self)

    def add_to_group(self, group):
        """
        food = Food(path=[food_id])
        fruit = Fruit(path=[fruit_id])
        
        If fruit.add_to_group(food._id):
            then update fruit.path to be [food_id, fruit_id]
        """
        group_id = group._id
        if group_id in self.path:
            raise Exception("Group %s is already a member of %s" % (
                self.get_id,
                group_id,
            ))
        new_path = [group_id]
        new_path.extend(self.path)
        self.path = new_path
        self.save()
    
    def remove_group(self, group):
        group.remove_from_group(self)

    def remove_from_group(self, group):
        """
        food = Food(path=[food_id])
        fruit = Fruit(path=[food_id, fruit_id])
        
        If fruit.remove_from_group(food._id):
            then update fruit.path to be [fruit_id]
        """
        group_id = group._id
        if group_id not in self.path:
            raise Exception("Group %s is not a member of %s" % (
                self.get_id,
                group_id
            ))
        index = 0
        for i in range(0,len(self.path)):
            if self.path[i] == group_id:
                index = i
                break
        self.path = self.path[index:]
        self.save()

    def get_user_ids(self, is_active=True):
        return [user.user_id for user in self.get_users(is_active)]

    def get_users(self, is_active=True, only_commcare=False):
        users = [CouchUser.get_by_user_id(user_id) for user_id in self.users]
        users = [user for user in users if not user.is_deleted()]
        if only_commcare is True:
            users = [
                user for user in users
                if user.__class__ == CommCareUser().__class__
            ]
        if is_active is True:
            return [user for user in users if user.is_active]
        else:
            return users

    @memoized
    def get_static_user_ids(self, is_active=True):
        return [user.user_id for user in self.get_static_users(is_active)]

    @memoized
    def get_static_users(self, is_active=True):
        return self.get_users()


    @classmethod
    def by_domain(cls, domain):
        return cls.view('groups/by_domain',
            key=domain,
            include_docs=True,
            stale=settings.COUCH_STALE_QUERY,
        ).all()

    @classmethod
    def by_name(cls, domain, name, one=True):
        result = cls.view('groups/by_name',
            key=[domain, name],
            include_docs=True,
            stale=settings.COUCH_STALE_QUERY,
        )
        if one:
            return result.one()
        else:
            return result

    @classmethod
    def by_user(cls, user_or_user_id, wrap=True, include_names=False):
        try:
            user_id = user_or_user_id.user_id
        except AttributeError:
            user_id = user_or_user_id
        results = cls.view('groups/by_user', key=user_id, include_docs=wrap)
        if wrap:
            return results
        if include_names:
            return [dict(group_id=r['id'], name=r['value'][1]) for r in results]
        else:
            return [r['id'] for r in results]

    @classmethod
    def by_user_type(cls, domain, type):
        """
        A group's user type consists of its user_type metadata property.
        
        """
        return cls.view(
                'groups/by_user_type', include_docs=True, reduce=False,
                key=[domain, type])

    @classmethod
    def by_hierarchy_type(cls, domain, type, owner_name=None):
        """
        A group's hierarchy type consists of its (owner_type, child_type)
        metadata.
        
        """
        view = partial(cls.view, 'groups/by_hierarchy_type', include_docs=True,
                reduce=False)
        key = [domain] + list(type)

        if owner_name:
            return view(key=key + [owner_name])
        else:
            return view(startkey=key, endkey=key + [{}])
    
    
    @classmethod
    def get_hierarchy(cls, domain, user_types, validate_types=False):
        """
        user_types -- a list of types corresponding to the levels of a tree of
            groups linked by their owner_type, child_type metadata and linked to
            users by their owner_name metadata (username).
            
            Example: ["supervisor", "team leader", "mobile worker"]

        validate_types -- whether to ensure that inner and leaf user nodes have
            the expected user types (by appearing in a group with the
            appropriate user_type metadata value)
        
        """
        user_types = list(user_types)

        # first get a dict keyed by the (owner_type, child_type) tuple (it
        # could just as well be a list in order) of dicts keyed by owner name
        # containing all groups that define this hierarchy type
        hierarchy_groups = {}

        for hierarchy_type in zip(user_types[:-1], user_types[1:]):
            groups = Group.by_hierarchy_type(domain, hierarchy_type)
            groups_by_owner = {}
            for g in groups:
                try:
                    groups_by_owner[g.metadata['owner_name']] = g
                except KeyError:
                    # Group found with hierarchy type information but no owner
                    # name
                    pass

            hierarchy_groups[hierarchy_type] = groups_by_owner

        # then construct a tree given root users, looking up each user owning
        # group by hierarchy_type + username 
        def get_descendants(user, user_types):
            hierarchy_type = tuple(user_types[0:2])
            hierarchy_type_groups = hierarchy_groups[hierarchy_type]
            try:
                child_group = hierarchy_type_groups[user.raw_username]
                child_users = child_group.get_users()
            except KeyError:  # the user doesn't have a child group
                child_group = None
                child_users = []

            if validate_types and child_users:
                child_type = hierarchy_type[1]
                group = cls.by_user_type(domain, child_type).first()
                if not group:
                    raise Exception("No group found for type %s" % child_type)
                for child in group.get_users():
                    if child not in users:
                        raise Exception("User and type don't match: %s, %s" %
                                (child.raw_username, child_type))
            ret = {
                "user": user,
                "child_group": child_group,
                "child_users": child_users,
            }
            
            if len(user_types) >= 3:
                user_types = user_types[1:]
                ret["descendants"] = [
                    get_descendants(c, user_types) for c in child_users]
            return ret

        root_group = cls.by_user_type(domain, user_types[0]).first()
        if not root_group:
            raise Exception("Unknown user type: %s" % user_types[0])

        root_users = root_group.get_users()

        return [get_descendants(u, user_types) for u in root_users]

    @classmethod
    def get_case_sharing_groups(cls, domain, wrap=True):
        all_groups = cls.by_domain(domain)
        if wrap:
            return [group for group in all_groups if group.case_sharing]
        else:
            return [group._id for group in all_groups if group.case_sharing]

    @classmethod
    def get_reporting_groups(cls, domain):
        key = ['^Reporting', domain]
        return cls.view('groups/by_name',
            startkey=key,
            endkey=key + [{}],
            include_docs=True,
            stale=settings.COUCH_STALE_QUERY,
        ).all()

    def create_delete_record(self, *args, **kwargs):
        return DeleteGroupRecord(*args, **kwargs)

    @property
    def display_name(self):
        if self.name:
            return self.name
        else:
            return "[No Name]"

    @classmethod
    def user_in_group(cls, user_id, group_id):
        if not user_id or not group_id:
            return False
        c = cls.get_db().view('groups/by_user',
            key=user_id,
            startkey_docid=group_id,
            endkey_docid=group_id
        ).count()
        if c == 0:
            return False
        elif c == 1:
            return True
        else:
            raise Exception(
                "This should just logically not be possible unless the group "
                "has the user in there twice"
            )

    def __repr__(self):
        return ("Group(domain={self.domain!r}, name={self.name!r}, "
                + "case_sharing={self.case_sharing!r}, users={users!r})"
        ).format(self=self, users=self.get_users())


class DeleteGroupRecord(DeleteDocRecord):
    def get_doc(self):
        return Group.get(self.doc_id)
