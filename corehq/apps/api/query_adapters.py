from dimagi.utils.chunked import chunked

from corehq.apps.es import GroupES, UserES
from corehq.apps.groups.models import Group
from corehq.apps.users.models import CommCareUser
from corehq.apps.users.user_data import prime_user_data_caches


class UserQuerySetAdapter(object):

    def __init__(self, domain, show_archived):
        self.domain = domain
        self.show_archived = show_archived

    def count(self):
        return self._query.count()

    __len__ = count

    @property
    def _query(self):
        if self.show_archived:
            return UserES().mobile_users().domain(self.domain).show_only_inactive().sort('username.exact')
        else:
            return UserES().mobile_users().domain(self.domain).sort('username.exact')

    def __getitem__(self, item):
        if isinstance(item, slice):
            limit = item.stop - item.start
            result = self._query.size(limit).start(item.start).run()
            users = (WrappedUser.wrap(user) for user in result.hits)
            return list(prime_user_data_caches(users, self.domain))
        raise ValueError(
            'Invalid type of argument. Item should be an instance of slice class.')


class WrappedUser(CommCareUser):

    @classmethod
    def wrap(cls, data):
        self = super().wrap(data)
        self._group_ids = sorted(data['__group_ids'])
        return self

    def get_group_ids(self):
        return self._group_ids


class GroupQuerySetAdapter(object):
    def __init__(self, domain):
        self.domain = domain

    def count(self):
        return GroupES().domain(self.domain).count()

    def __getitem__(self, item):
        if isinstance(item, slice):
            limit = item.stop - item.start
            result = GroupES().domain(self.domain).sort('name.exact').size(limit).start(item.start).run()
            groups = [WrappedGroup.wrap(group) for group in result.hits]

            active_user_ids = set(self._iter_active_user_ids(groups))
            for group in groups:
                group._precomputed_active_users = [
                    user_id for user_id in group.users
                    if user_id in active_user_ids
                ]
            return groups
        raise ValueError(
            'Invalid type of argument. Item should be an instance of slice class.')

    def _iter_active_user_ids(self, groups):
        all_user_ids = {user_id for group in groups for user_id in group.users}
        for user_ids_chunk in chunked(all_user_ids, 1000):
            yield from (
                UserES().domain(self.domain)
                .user_ids(user_ids_chunk)
                .is_active(True)
                .values_list('_id', flat=True)
            )


class WrappedGroup(Group):
    _precomputed_active_users = None

    def get_user_ids(self, is_active=True):
        if is_active is not True:
            raise ValueError(
                "Unexpected call of Group.get_user_ids(is_active=False) in read API context")
        if self._precomputed_active_users is None:
            raise ValueError(
                "In the Group API read context, you must set group._precomputed_active_users "
                "before calling group.get_user_ids"
            )
        return self._precomputed_active_users
