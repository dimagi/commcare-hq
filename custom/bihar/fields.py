from __future__ import absolute_import
from corehq.apps.groups.models import Group
from corehq.apps.reports.filters.select import GroupFilter


class SelectCaseSharingGroupField(GroupFilter):

    def update_params(self):
        super(SelectCaseSharingGroupField, self).update_params()
        self.groups = Group.get_case_sharing_groups(self.domain)
        self.options = [dict(val=group.get_id, text=group.name) for group in self.groups]
