from collections import defaultdict
from itertools import chain

from django.utils.translation import gettext as _

from corehq.apps.api.es import flatten_list
from corehq.apps.es import filters
from corehq.apps.es.aggregations import TermsAggregation
from corehq.apps.es.cases import CaseES
from corehq.apps.es.users import UserES
from corehq.apps.groups.models import Group
from corehq.apps.locations.models import SQLLocation
from corehq.apps.users.audit.change_messages import UserChangeMessage
from corehq.apps.users.models import (
    DomainMembershipError,
    StaticRole,
    UserRole,
)
from corehq.apps.users.util import log_user_change
from corehq.const import USER_CHANGE_VIA_WEB
from corehq.util.quickcache import quickcache


def get_editable_role_choices(domain, couch_user, allow_admin_role):
    """
    :param domain: roles for domain
    :param couch_user: user accessing the roles
    :param allow_admin_role: to include admin role, in case user is admin
    """
    roles = [role for role in UserRole.objects.get_by_domain(domain)
             if not role.is_commcare_user_default]
    if not couch_user.is_domain_admin(domain):
        try:
            user_role = couch_user.get_role(domain)
        except DomainMembershipError:
            user_role = None
        user_role_id = user_role.get_id if user_role else None
        roles = [
            role for role in roles
            if role.accessible_by_non_admin_role(user_role_id)
        ]
    elif allow_admin_role:
        roles = [StaticRole.domain_admin(domain)] + roles
    return sorted([
        (role.get_qualified_id(), role.name or _('(No Name)'))
        for role in roles
    ], key=lambda c: c[1].lower())


class BulkUploadResponseWrapper(object):

    def __init__(self, context):
        results = context.get('result') or defaultdict(lambda: [])
        self.response_rows = results['rows']
        self.response_errors = results['errors']
        if context['user_type'] == 'web users':
            self.problem_rows = [r for r in self.response_rows if r['flag'] not in ('updated', 'invited')]
        else:
            self.problem_rows = [r for r in self.response_rows if r['flag'] not in ('updated', 'created')]

    def success_count(self):
        return len(self.response_rows) - len(self.problem_rows)

    def has_errors(self):
        return bool(self.response_errors or self.problem_rows)

    def errors(self):
        errors = []
        for row in self.problem_rows:
            if row['flag'] == 'missing-data':
                errors.append(_('A row with no username was skipped'))
            else:
                errors.append('{username}: {flag}'.format(**row))
        errors.extend(self.response_errors)
        return errors


def log_user_groups_change(domain, request, user, group_ids=None):
    groups = []
    # no groups assigned would be group ids as []
    # so if group ids were NOT passed or if some were passed, get groups for user
    if group_ids is None or group_ids:
        groups = Group.by_user_id(user.get_id)
    log_user_change(
        by_domain=domain,
        for_domain=domain,  # Groups are bound to a domain, so use domain
        couch_user=user,
        changed_by_user=request.couch_user,
        changed_via=USER_CHANGE_VIA_WEB,
        change_messages=UserChangeMessage.groups_info(groups)
    )


def log_commcare_user_locations_changes(request, user, old_location_id, old_assigned_location_ids):
    change_messages = {}
    fields_changed = {}
    if old_location_id != user.location_id:
        location = None
        fields_changed['location_id'] = user.location_id
        if user.location_id:
            location = SQLLocation.objects.get(location_id=user.location_id)
        change_messages.update(UserChangeMessage.primary_location_info(location))
    if old_assigned_location_ids != user.assigned_location_ids:
        locations = []
        fields_changed['assigned_location_ids'] = user.assigned_location_ids
        if user.assigned_location_ids:
            locations = SQLLocation.objects.filter(location_id__in=user.assigned_location_ids)
        change_messages.update(UserChangeMessage.assigned_locations_info(locations))

    if change_messages:
        log_user_change(
            by_domain=request.domain,
            for_domain=user.domain,
            couch_user=user,
            changed_by_user=request.couch_user,
            changed_via=USER_CHANGE_VIA_WEB,
            fields_changed=fields_changed,
            change_messages=change_messages
        )


@quickcache(['domain', 'location_ids', 'user_id_to_exclude'], timeout=10)
def _get_location_ids_with_other_users(domain, location_ids, user_id_to_exclude):
    """
    Gets all the location ids where a `CommCareUser` is assigned to one of the `location_ids`.
    This list excludes the given `user_id`.
    """
    other_user_loc_ids = (
        UserES()
        .domain(domain)
        .mobile_users()
        .NOT(filters.doc_id(user_id_to_exclude))
        .location(location_ids)
        .values_list('assigned_location_ids', flat=True)
    )
    # If more than one user shares a location, it will give a list of lists
    # So need to make sure to flatten these
    return set(flatten_list(other_user_loc_ids))


def _get_location_case_counts(domain, location_ids):
    """
    Get the case count for all locations in `location_ids`
    :returns A dict with location_id as the key and the case count as the value
    """
    query = (
        CaseES()
        .domain(domain)
        .owner(location_ids)
        .aggregation(TermsAggregation('by_location', 'owner_id'))
    ).run()
    counts = query.aggregations.by_location.counts_by_bucket()

    return counts


def _get_locations_with_orphaned_cases(domain, location_ids, user_id):
    """
    Takes a list of location IDs and returns all the given location IDs
    where the user ID is the only one that has cases there. Also searched through descendant locations
    if a location has `view_descendants` enabled.
    :param domain: The domain to search in.
    :param location_ids: A list of location IDs to get case counts on.
    :param user_id: The user ID to check given `location_ids` with as the only assigned user with cases.
    :returns A dict with location names as the key, and the number of cases assigned to them as the value.
    """
    loc_ids_with_other_users = _get_location_ids_with_other_users(domain, location_ids, user_id)

    # Get the assigned location ids that are in all_loc_ids but not in loc_ids_with_other_users
    orphaned_loc_ids = list(set(location_ids) - loc_ids_with_other_users)
    if not orphaned_loc_ids:
        return {}

    assigned_locs = SQLLocation.objects.filter(location_id__in=orphaned_loc_ids)
    # We need to find all descendant locations for orphaned assigned locations that don't have a user
    # assigned to them
    desc_locs = SQLLocation.objects.get_queryset_descendants(
        assigned_locs.filter(location_type__view_descendants=True)
    )
    desc_loc_ids = [loc.location_id for loc in desc_locs]
    desc_loc_ids_with_other_users = _get_location_ids_with_other_users(domain, desc_loc_ids, user_id)
    orphaned_desc_loc_ids = list(set(desc_loc_ids) - desc_loc_ids_with_other_users)

    all_orphaned_loc_ids = set(orphaned_loc_ids + orphaned_desc_loc_ids)
    all_locs = set(chain(assigned_locs, desc_locs))
    case_count_per_loc = _get_location_case_counts(domain, all_orphaned_loc_ids)
    return {
        loc.get_path_display(): case_count_per_loc[loc.location_id] for loc in all_locs
        if loc.location_id in case_count_per_loc
    }


def get_user_location_info(domain, user_location_ids, user_id):
    shared_locations = _get_location_ids_with_other_users(
        domain,
        user_location_ids,
        user_id
    )

    orphaned_case_count_per_location = _get_locations_with_orphaned_cases(
        domain,
        user_location_ids,
        user_id
    )
    return {
        'orphaned_case_count_per_location': orphaned_case_count_per_location,
        'shared_locations': shared_locations,
    }
