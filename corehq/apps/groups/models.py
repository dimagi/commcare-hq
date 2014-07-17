from __future__ import absolute_import
from couchdbkit.ext.django.schema import *
from dimagi.utils.couch.database import iter_docs
from dimagi.utils.decorators.memoized import memoized
from corehq.apps.users.models import CouchUser, CommCareUser
from dimagi.utils.couch.undo import UndoableDocument, DeleteDocRecord, DELETED_SUFFIX
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
        return self.get_users(is_active)


    @classmethod
    def by_domain(cls, domain):
        return cls.view('groups/by_domain',
            key=domain,
            include_docs=True,
            #stale=settings.COUCH_STALE_QUERY,
        ).all()

    @classmethod
    def choices_by_domain(cls, domain):
        group_ids = cls.ids_by_domain(domain)
        group_choices = []
        for group_doc in iter_docs(cls.get_db(), group_ids):
            group_choices.append((group_doc['_id'], group_doc['name']))
        return group_choices

    @classmethod
    def ids_by_domain(cls, domain):
        return [r['id'] for r in cls.get_db().view('groups/by_domain',
            key=domain,
            include_docs=False,
        )]

    @classmethod
    def by_name(cls, domain, name, one=True):
        result = cls.view('groups/by_name',
            key=[domain, name],
            include_docs=True,
            #stale=settings.COUCH_STALE_QUERY,
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
            #stale=settings.COUCH_STALE_QUERY,
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

    def is_member_of(self, domain):
        return self.domain == domain

    @property
    def is_deleted(self):
        return self.doc_type.endswith(DELETED_SUFFIX)

    def __repr__(self):
        return ("Group(domain={self.domain!r}, name={self.name!r}, "
                + "case_sharing={self.case_sharing!r}, users={users!r})"
        ).format(self=self, users=self.get_users())


class DeleteGroupRecord(DeleteDocRecord):
    def get_doc(self):
        return Group.get(self.doc_id)
