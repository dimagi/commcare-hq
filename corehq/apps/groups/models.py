from __future__ import absolute_import
from __future__ import unicode_literals
from six.moves import map

from django.conf import settings

from dimagi.ext.couchdbkit import *
import re
from dimagi.utils.couch.database import iter_docs
from memoized import memoized
from corehq.apps.cachehq.mixins import QuickCachedDocumentMixin
from corehq.apps.users.models import CouchUser, CommCareUser
from dimagi.utils.couch.undo import UndoableDocument, DeleteDocRecord, DELETED_SUFFIX
from datetime import datetime
from corehq.apps.groups.dbaccessors import (
    get_group_ids_by_domain,
    group_by_domain,
    refresh_group_views,
    stale_group_by_name,
)
from corehq.apps.locations.models import SQLLocation
from corehq.apps.groups.exceptions import CantSaveException
from corehq.util.python_compatibility import soft_assert_type_text
from corehq.util.quickcache import quickcache
import six
from six.moves import range
from six.moves import filter

dt_no_Z_re = re.compile(r'^\d\d\d\d-\d\d-\d\dT\d\d:\d\d:\d\d(\.\d\d\d\d\d\d)?$')


class Group(QuickCachedDocumentMixin, UndoableDocument):
    """
    The main use case for these 'groups' of users is currently
    so that we can break down reports by arbitrary regions.

    (Things like who sees what reports are determined by permissions.)
    """
    domain = StringProperty()
    name = StringProperty()
    # a list of user ids for users
    users = ListProperty()
    # a list of user ids that have been removed from the Group.
    # This is recorded so that we can update the user at a later point
    removed_users = SetProperty()
    path = ListProperty()
    case_sharing = BooleanProperty()
    reporting = BooleanProperty(default=True)
    last_modified = DateTimeProperty()

    # custom data can live here
    metadata = DictProperty()

    @classmethod
    def wrap(cls, data):
        last_modified = data.get('last_modified')
        # if it's missing a Z because of the Aug. 2014 migration
        # that added this in iso_format() without Z, then add a Z
        if last_modified and dt_no_Z_re.match(last_modified):
            data['last_modified'] += 'Z'
        return super(Group, cls).wrap(data)

    def save(self, *args, **kwargs):
        self.last_modified = datetime.utcnow()
        super(Group, self).save(*args, **kwargs)
        refresh_group_views()

    @classmethod
    def save_docs(cls, docs, use_uuids=True):
        utcnow = datetime.utcnow()
        for doc in docs:
            doc['last_modified'] = utcnow
        super(Group, cls).save_docs(docs, use_uuids)
        refresh_group_views()

    bulk_save = save_docs

    def delete(self):
        super(Group, self).delete()
        refresh_group_views()

    @classmethod
    def delete_docs(cls, docs, **params):
        super(Group, cls).delete_docs(docs, **params)
        refresh_group_views()

    bulk_delete = delete_docs

    def clear_caches(self):
        super(Group, self).clear_caches()
        self.by_domain.clear(self.__class__, self.domain)
        self.ids_by_domain.clear(self.__class__, self.domain)

    def add_user(self, couch_user_id, save=True):
        if not isinstance(couch_user_id, six.string_types):
            couch_user_id = couch_user_id.user_id
        else:
            soft_assert_type_text(couch_user_id)
        soft_assert_type_text(couch_user_id)
        if couch_user_id not in self.users:
            self.users.append(couch_user_id)
        if couch_user_id in self.removed_users:
            self.removed_users.remove(couch_user_id)
        if save:
            self.save()

    def remove_user(self, couch_user_id):
        '''
        Returns True if it removed a user, False otherwise
        '''
        if not isinstance(couch_user_id, six.string_types):
            couch_user_id = couch_user_id.user_id
        else:
            soft_assert_type_text(couch_user_id)
        soft_assert_type_text(couch_user_id)
        if couch_user_id in self.users:
            for i in range(0, len(self.users)):
                if self.users[i] == couch_user_id:
                    del self.users[i]
                    self.removed_users.add(couch_user_id)
                    return True
        return False

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
        for i in range(0, len(self.path)):
            if self.path[i] == group_id:
                index = i
                break
        self.path = self.path[index:]
        self.save()

    def get_user_ids(self, is_active=True):
        return [user.user_id for user in self.get_users(is_active=is_active)]

    @memoized
    def get_users(self, is_active=True, only_commcare=False):
        def is_relevant_user(user):
            if user.is_deleted():
                return False
            if only_commcare and user.__class__ != CommCareUser().__class__:
                return False
            if is_active and not user.is_active:
                return False
            return True
        users = map(CouchUser.wrap_correctly, iter_docs(self.get_db(), self.users))
        return list(filter(is_relevant_user, users))

    @memoized
    def get_static_user_ids(self, is_active=True):
        return [user.user_id for user in self.get_static_users(is_active)]

    @classmethod
    def get_static_user_ids_for_groups(cls, group_ids):
        static_user_ids = []
        for group_id in group_ids:
            group = cls.get(group_id)
            static_user_ids.append(group.get_static_user_ids())
        return static_user_ids

    @memoized
    def get_static_users(self, is_active=True):
        return self.get_users(is_active)

    @classmethod
    @quickcache(['cls.__name__', 'domain'])
    def by_domain(cls, domain):
        return group_by_domain(domain)

    @classmethod
    def choices_by_domain(cls, domain):
        group_ids = cls.ids_by_domain(domain)
        group_choices = []
        for group_doc in iter_docs(cls.get_db(), group_ids):
            group_choices.append((group_doc['_id'], group_doc['name']))
        return group_choices

    @classmethod
    @quickcache(['cls.__name__', 'domain'])
    def ids_by_domain(cls, domain):
        return get_group_ids_by_domain(domain)

    @classmethod
    def by_name(cls, domain, name, one=True):
        result = stale_group_by_name(domain, name)
        if one and result:
            return result[0]
        else:
            return result

    @classmethod
    def by_user_id(cls, user_id, wrap=True, include_names=False):
        results = cls.view('groups/by_user', key=user_id, include_docs=wrap)
        if wrap:
            return results
        if include_names:
            return [dict(group_id=r['id'], name=r['value'][1]) for r in results]
        else:
            return [r['id'] for r in results]

    @classmethod
    def get_case_sharing_accessible_locations(cls, domain, user):
        return [
            location.case_sharing_group_object() for location in
            SQLLocation.objects.accessible_to_user(domain, user).filter(location_type__shares_cases=True)
        ]

    @classmethod
    def get_case_sharing_groups(cls, domain, wrap=True):
        all_groups = cls.by_domain(domain)
        if wrap:
            groups = [group for group in all_groups if group.case_sharing]
            groups.extend([
                location.case_sharing_group_object() for location in
                SQLLocation.objects.filter(domain=domain,
                                           location_type__shares_cases=True)
            ])
            return groups
        else:
            return [group._id for group in all_groups if group.case_sharing]

    @classmethod
    def get_reporting_groups(cls, domain):
        key = ['^Reporting', domain]
        return cls.view(
            'groups/by_name',
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

    def is_member_of(self, domain):
        return self.domain == domain

    @property
    def is_deleted(self):
        return self.doc_type.endswith(DELETED_SUFFIX)

    def __repr__(self):
        return ("Group(domain={self.domain!r}, name={self.name!r}, "
                "case_sharing={self.case_sharing!r})").format(self=self)


class UnsavableGroup(Group):

    def save(self, *args, **kwargs):
        raise CantSaveException("Instances of UnsavableGroup cannot be saved")


class DeleteGroupRecord(DeleteDocRecord):

    def get_doc(self):
        return Group.get(self.doc_id)
