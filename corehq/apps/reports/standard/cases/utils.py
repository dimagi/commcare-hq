from __future__ import absolute_import
from __future__ import unicode_literals

from corehq.apps.locations.dbaccessors import (
    user_ids_at_locations,
    user_ids_at_locations_and_descendants,
    get_users_location_ids,
)
from corehq.apps.locations.models import SQLLocation
from corehq.apps.reports.models import HQUserType
from corehq.apps.reports.filters.case_list import CaseListFilter as EMWF
from corehq.apps.es import (
    filters,
    users as user_es,
    cases as case_es,
)
from corehq.apps.es.es_query import HQESQuery


def _get_special_owner_ids(domain, admin, unknown, web, demo, commtrack):
    if not any([admin, unknown, web, demo, commtrack]):
        return []

    user_filters = [filter_ for include, filter_ in [
        (admin, user_es.admin_users()),
        (unknown, filters.OR(user_es.unknown_users())),
        (web, user_es.web_users()),
        (demo, user_es.demo_users()),
    ] if include]

    owner_ids = (user_es.UserES()
                 .domain(domain)
                 .OR(*user_filters)
                 .get_ids())

    if commtrack:
        owner_ids.append("commtrack-system")
    if demo:
        owner_ids.append("demo_user_group_id")
        owner_ids.append("demo_user")
    return owner_ids


def query_all_project_data(query, domain, mobile_user_and_group_slugs):
    # Show everything but stuff we know for sure to exclude
    user_types = EMWF.selected_user_types(mobile_user_and_group_slugs)
    ids_to_exclude = _get_special_owner_ids(
        domain=domain,
        admin=HQUserType.ADMIN not in user_types,
        unknown=HQUserType.UNKNOWN not in user_types,
        web=HQUserType.WEB not in user_types,
        demo=HQUserType.DEMO_USER not in user_types,
        commtrack=False,
    )
    return query.NOT(case_es.owner(ids_to_exclude))


def query_deactivated_data(query, domain):
    owner_ids = (user_es.UserES()
                 .show_only_inactive()
                 .domain(domain)
                 .get_ids())
    return query.OR(case_es.owner(owner_ids))


def get_case_owners(request, domain, mobile_user_and_group_slugs):
    """
    For unrestricted user
    :return:
    user ids for selected user types
    for selected reporting group ids, returns user_ids belonging to these groups
        also finds the sharing groups which has any user from the above reporting group
    selected sharing group ids
    selected user ids
        also finds the sharing groups which has any user from the above selected users
        ids and descendants ids of assigned locations to these users
    ids and descendants ids of selected locations
        assigned users at selected locations and their descendants

    For restricted user
    :return:
    selected user ids
        also finds the sharing groups which has any user from the above selected users
        ids and descendants ids of assigned locations to these users
    ids and descendants ids of selected locations
        assigned users at selected locations and their descendants
    """
    special_owner_ids, selected_sharing_group_ids, selected_reporting_group_users = [], [], []
    sharing_group_ids, location_owner_ids, assigned_user_ids_at_selected_locations = [], [], []

    if request.can_access_all_locations:
        user_types = EMWF.selected_user_types(mobile_user_and_group_slugs)

        special_owner_ids = _get_special_owner_ids(
            domain=domain,
            admin=HQUserType.ADMIN in user_types,
            unknown=HQUserType.UNKNOWN in user_types,
            web=HQUserType.WEB in user_types,
            demo=HQUserType.DEMO_USER in user_types,
            commtrack=HQUserType.COMMTRACK in user_types,
        )

        # Get group ids for each group that was specified
        selected_reporting_group_ids = EMWF.selected_reporting_group_ids(
            mobile_user_and_group_slugs)
        selected_sharing_group_ids = EMWF.selected_sharing_group_ids(
            mobile_user_and_group_slugs)

        # Get user ids for each user in specified reporting groups
        selected_reporting_group_users = []
        if selected_reporting_group_ids:
            report_group_q = (
                HQESQuery(index="groups").domain(domain).doc_type("Group").filter(
                    filters.term(
                        "_id", selected_reporting_group_ids
                    )).fields(["users"])
            )
            user_lists = [group["users"] for group in report_group_q.run().hits]
            selected_reporting_group_users = list(set().union(*user_lists))

    # Get user ids for each user that was specifically selected
    selected_user_ids = EMWF.selected_user_ids(mobile_user_and_group_slugs)

    # Show cases owned by any selected locations, user locations, or their children
    loc_ids = set(EMWF.selected_location_ids(mobile_user_and_group_slugs))

    if loc_ids:
        # Get users at selected locations and descendants
        assigned_user_ids_at_selected_locations = user_ids_at_locations_and_descendants(
            loc_ids)
        # Get user ids for each user in specified reporting groups

    if selected_user_ids:
        loc_ids.update(get_users_location_ids(domain, selected_user_ids))

    location_owner_ids = []
    if loc_ids:
        location_owner_ids = SQLLocation.objects.get_locations_and_children_ids(
            loc_ids)

    sharing_group_ids = []
    if selected_reporting_group_users or selected_user_ids:
        # Get ids for each sharing group that contains a user from
        # selected_reporting_group_users OR a user that was specifically selected
        sharing_group_ids = (HQESQuery(index="groups")
                             .domain(domain)
                             .doc_type("Group")
                             .term("case_sharing", True)
                             .term("users", (selected_reporting_group_users +
                                             selected_user_ids))
                             .get_ids())

    owner_ids = list(set().union(
        special_owner_ids,
        selected_user_ids,
        selected_sharing_group_ids,
        selected_reporting_group_users,
        sharing_group_ids,
        location_owner_ids,
        assigned_user_ids_at_selected_locations,
    ))
    return owner_ids


def _get_location_accessible_ids(request):
    accessible_location_ids = (SQLLocation.active_objects.accessible_location_ids(
        request.domain,
        request.couch_user
    ))
    accessible_user_ids = user_ids_at_locations(accessible_location_ids)
    accessible_ids = accessible_user_ids + list(accessible_location_ids)
    return accessible_ids


def query_location_restricted_cases(query, request):
    accessible_ids = _get_location_accessible_ids(request)
    return query.OR(case_es.owner(accessible_ids))
