from corehq.apps.es import cases as case_es
from corehq.apps.es import filters
from corehq.apps.es import users as user_es
from corehq.apps.es import forms as form_es
from corehq.apps.es.es_query import HQESQuery
from corehq.apps.locations.dbaccessors import (
    get_users_location_ids,
    mobile_user_ids_at_locations,
    user_ids_at_locations_and_descendants,
)
from corehq.apps.locations.models import SQLLocation
from corehq.apps.reports.exceptions import TooManyOwnerIDsError
from corehq.apps.reports.filters.case_list import CaseListFilter as EMWF
from corehq.apps.reports.models import HQUserType
from corehq.apps.hqwebapp.doc_info import get_doc_info_by_id
from corehq.apps.hqcase.utils import SYSTEM_FORM_XMLNS_MAP
from corehq.project_limits.const import OWNER_ID_LIMIT_KEY, DEFAULT_OWNER_ID_LIMIT
from corehq.project_limits.models import SystemLimit


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


def all_project_data_filter(domain, mobile_user_and_group_slugs):
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
    return filters.NOT(case_es.owner(ids_to_exclude))


def deactivated_case_owners(domain):
    owner_ids = (user_es.UserES()
                 .domain(domain, include_active=False, include_inactive=True)
                 .get_ids())
    return case_es.owner(owner_ids)


def get_case_owners(can_access_all_locations, domain, mobile_user_and_group_slugs):
    """
    Returns a list of user, group, and location ids that are owners for cases.

    :param can_access_all_locations: boolean
        - generally obtained from `request.can_access_all_locations`
    :param domain: string
        - the domain string that the case owners belong to
    :param mobile_user_and_group_slugs: list
        - a list of user ids and special formatted strings returned by
          the `ExpandedMobileWorkerFilter` and its subclasses

    For unrestricted user (can_access_all_locations = True)
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

    For restricted user (can_access_all_locations = False)
    :return:
    selected user ids
        also finds the sharing groups which has any user from the above selected users
        ids and descendants ids of assigned locations to these users
    ids and descendants ids of selected locations
        assigned users at selected locations and their descendants
    """
    special_owner_ids, selected_sharing_group_ids, selected_reporting_group_users = [], [], []
    sharing_group_ids, location_owner_ids, assigned_user_ids_at_selected_locations = [], [], []

    if can_access_all_locations:
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
            selected_reporting_group_users = set()
            for element in user_lists:
                if isinstance(element, list):
                    # Groups containing multiple users will be returned as a list.
                    selected_reporting_group_users |= set(element)
                else:
                    # Groups containing a single user will be returned as single elements in query.
                    selected_reporting_group_users.add(element)
            selected_reporting_group_users = list(selected_reporting_group_users)

    # Get user ids for each user that was specifically selected
    selected_user_ids = EMWF.selected_user_ids(mobile_user_and_group_slugs)

    # Show cases owned by any selected locations, user locations, or their children
    loc_ids = set(EMWF.selected_location_ids(mobile_user_and_group_slugs))

    if loc_ids:
        # Get users at selected locations and descendants
        assigned_user_ids_at_selected_locations = user_ids_at_locations_and_descendants(domain, loc_ids)
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
                             .term("users", (selected_reporting_group_users + selected_user_ids))
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
    limit = SystemLimit.get_limit_for_key(OWNER_ID_LIMIT_KEY, DEFAULT_OWNER_ID_LIMIT, domain=domain)
    if len(owner_ids) > limit:
        raise TooManyOwnerIDsError
    return owner_ids


def _get_location_accessible_ids(domain, couch_user):
    accessible_location_ids = (SQLLocation.active_objects.accessible_location_ids(
        domain,
        couch_user
    ))
    accessible_user_ids = mobile_user_ids_at_locations(domain, accessible_location_ids)
    accessible_ids = accessible_user_ids + list(accessible_location_ids)
    return accessible_ids


def query_location_restricted_cases(query, domain, couch_user):
    accessible_ids = _get_location_accessible_ids(domain, couch_user)
    return query.filter(case_es.owner(accessible_ids))


def query_location_restricted_forms(query, domain, couch_user):
    accessible_ids = _get_location_accessible_ids(domain, couch_user)
    return query.filter(form_es.user_id(accessible_ids))


def get_user_type(form, domain=None):
    user_type = 'Unknown'
    if getattr(form.metadata, 'username', None) == 'system':
        if form.xmlns in SYSTEM_FORM_XMLNS_MAP:
            user_type = SYSTEM_FORM_XMLNS_MAP[form.xmlns]
        else:
            user_type = 'System'
    elif getattr(form.metadata, 'userID', None):
        doc_info = get_doc_info_by_id(domain, form.metadata.userID)
        if doc_info.type_display:
            user_type = doc_info.type_display

    return user_type


def add_case_owners_and_location_access(
    query,
    domain,
    couch_user,
    can_access_all_locations,
    mobile_user_and_group_slugs
):
    case_owner_filters = []

    if can_access_all_locations:
        if EMWF.show_project_data(mobile_user_and_group_slugs):
            case_owner_filters.append(all_project_data_filter(domain, mobile_user_and_group_slugs))
        if EMWF.show_deactivated_data(mobile_user_and_group_slugs):
            case_owner_filters.append(deactivated_case_owners(domain))

    # Only show explicit matches
    if (
        EMWF.selected_user_ids(mobile_user_and_group_slugs)
        or EMWF.selected_user_types(mobile_user_and_group_slugs)
        or EMWF.selected_group_ids(mobile_user_and_group_slugs)
        or EMWF.selected_location_ids(mobile_user_and_group_slugs)
    ):
        case_owners = get_case_owners(can_access_all_locations, domain, mobile_user_and_group_slugs)
        case_owner_filters.append(case_es.owner(case_owners))

    query = query.OR(*case_owner_filters)

    if not can_access_all_locations:
        query = query_location_restricted_cases(query, domain, couch_user)
    return query
