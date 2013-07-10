from django.utils.translation import ugettext_noop
from django.utils.translation import ugettext as _

from corehq.apps.reports.filters.base import BaseDrilldownOptionFilter
from corehq.apps.groups.hierarchy import (get_hierarchy,
        get_leaf_user_ids_from_hierarchy)


class LinkedUserFilter(BaseDrilldownOptionFilter):
    """
    Lets you define hierarchical user groups by adding semantics to the
    following group metadata properties:

    On the root user group containing the top-level users:
        user_type:  name of user type

    On each group defining an association between one level-N user and many
    level-N+1 users:
        owner_name:  username of the owning user
        owner_type:  name of user type for the owner
        child_type:  name of user type for the child

    Then you define the user_types attribute of this class as a list of user
    types.

    """
    slug = "user"
    label = ugettext_noop("Select User(s)")

    # (parent_type, child_type[, child_type...]) as defined in the
    # user-editable group metadata
    user_types = None
    domain = None

    # Whether to use group names for intermediate selectors instead of the
    # username of the group's owner
    use_group_names = False

    @classmethod
    def get_labels(cls):
        for type in cls.user_types:
            yield (
                type,
                _("Select %(child_type)s") % {'child_type': type}, 
                type
            )

    @property
    def drilldown_empty_text(self):
        return _("An error occured while making this linked user "
                 "filter. Make sure you have created a group containing "
                 "all %(root_type)ss with the metadata property 'user_type' set "
                 "to '%(root_type)s' and added owner_type and child_type "
                 "metadata properties to all of the necessary other groups.") % {
            "root_type": self.user_types[0]
        }

    @property
    def drilldown_map(self):
        try:
            hierarchy = get_hierarchy(self.domain, self.user_types)
        except Exception:
            return []

        def get_values(node, level):
            ret = {
                'val': node['user']._id
            }
            if node.get('child_group') and self.use_group_names:
                ret['text'] = node['child_group'].name
            else:
                ret['text'] = node['user'].raw_username

            if 'descendants' in node:
                ret['next'] = [get_values(node, level + 1) 
                               for node in node['descendants']]
            elif node.get('child_users'):
                ret['next'] = [{
                    'val': c._id,
                    'text': c.raw_username
                } for c in node['child_users']]
            else:
                ret['next'] = [{
                    'val': '',
                    'text': _("No %(child_type)ss found for this %(parent_type)s.") % {
                                'parent_type': self.user_types[level],
                                'child_type': self.user_types[level + 1]}
                }]

            return ret

        return [get_values(top_level_node, 0) for top_level_node in hierarchy]

    @classmethod
    def get_user_ids(cls, request_params, domain=None):
        domain = domain or cls.domain

        selected_user_id = None

        for user_type in reversed(cls.user_types):
            user_id = request_params.get("%s_%s" % (cls.slug, user_type))
            if user_id:
                selected_user_id = user_id
                break

        return get_leaf_user_ids_from_hierarchy(domain, cls.user_types,
                root_user_id=selected_user_id)
