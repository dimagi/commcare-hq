import datetime, pytz

from celery.task import periodic_task
from celery.schedules import crontab
from django.conf import settings
from xml.etree import ElementTree

from casexml.apps.case.models import CommCareCase
from casexml.apps.case.mock import CaseBlock
from casexml.apps.case.xml import V2
from corehq.apps.domain.models import Domain
from corehq.apps.fixtures.models import FixtureDataItem
from corehq.apps.groups.models import Group
from corehq.apps.hqcase.utils import submit_case_blocks, get_cases_in_domain
from dimagi.utils.decorators.memoized import memoized

DOMAINS = ["hsph-dev", "hsph-betterbirth"]
PAST_N_DAYS = 21
GROUPS_TO_CHECK = ["cati", "cati-tl"]
GROUP_SHOULD_BE = "fida"
TYPE = "birth"
OWNER_FIELD_MAPPINGS = {
        "cati": "cati_assignment",
        "fida": "field_follow_up_assignment"
    }
INDEXED_GROUPS = dict((domain, {}) for domain in DOMAINS)

@memoized
def indexed_fixtures():
    return dict((domain, FixtureDataItem.get_indexed_items(domain, "site", "site_id")) for domain in DOMAINS)


def update_groups_index(domain):
    groups = Group.by_domain(domain)
    for group in groups:
        if group.case_sharing and group.metadata.get("main_user", None):
            INDEXED_GROUPS[domain][group.metadata["main_user"]] = group


def get_owner_username(domain, owner_type, site_id):
    INDEXED_FIXTURES = indexed_fixtures()
    if not owner_type:
        return ''
    field_name = OWNER_FIELD_MAPPINGS[owner_type]
    try:
        return INDEXED_FIXTURES[domain][site_id][field_name]
    except KeyError:
        return None


def get_group_id(domain, owner_type, site_id):
    owner_username = get_owner_username(domain, owner_type, site_id)
    try:
        return INDEXED_GROUPS[domain][owner_username]._id
    except KeyError:
        return None

past_x_date = lambda time_zone, past_x_days: (datetime.datetime.now(time_zone) - datetime.timedelta(past_x_days)).date()
get_none_or_value = lambda _object, _attribute: getattr(_object, _attribute) if (hasattr(_object, _attribute)) else ''


@periodic_task(
    run_every=crontab(minute=1, hour=0),
    queue=getattr(settings, 'CELERY_PERIODIC_QUEUE', 'celery')
)
def new_update_case_properties():
    _domain = Domain.get_by_name(DOMAINS[0])
    if _domain is None:
        return
    time_zone = _domain.default_timezone
    time_zone = pytz.timezone(time_zone)
    past_21_date = past_x_date(time_zone, 21)
    past_42_date = past_x_date(time_zone, 42)
    for domain in DOMAINS:
        update_groups_index(domain)
        case_list = get_cases_in_domain(domain, type=TYPE)
        cases_to_modify = []
        for case in case_list:
            if case.closed:
                continue
            if not get_none_or_value(case, "owner_id") or not get_none_or_value(case, "date_admission") or not get_none_or_value(case, "site_id"):
                continue
            curr_assignment = get_none_or_value(case, "current_assignment")
            next_assignment = get_none_or_value(case, "next_assignment")
            site_id = case.site_id
            fida_group = get_group_id(domain, "fida", site_id)
            cati_owner_username = get_owner_username(domain, "cati", site_id)

            ## Assignment Directly from Registration ##
            # Assign Cases to Call Center
            if case.date_admission >= past_21_date and (not curr_assignment) and (not next_assignment):
                owner_id = get_group_id(domain, "cati", site_id)
                if not owner_id:
                    continue
                update = {
                    "owner_id": owner_id,
                    "current_assignment": "cati"
                }
                cases_to_modify.append({
                    "case_id": case._id,
                    "update": update,
                    "close": False,
                })
            # Assign Cases Directly To Field
            elif (case.date_admission >= past_42_date) and (case.date_admission < past_21_date) and (not curr_assignment) and (not next_assignment):
                if not fida_group:
                    continue
                update = {
                    "current_assignment": "fida",
                    "owner_id": fida_group,                   
                    "cati_status": 'skipped',
                }
                cases_to_modify.append(
                    {
                        "case_id": case._id,
                        "update": update,
                        "close": False,
                    }
                )
            # Assign Cases Directly to Lost to Follow Up
            elif case.date_admission < past_42_date and (not curr_assignment) and (not next_assignment):
                update = {
                    "cati_status": 'skipped',
                    "last_assignment": '',
                    "closed_status": "timed_out_lost_to_follow_up",
                }
                cases_to_modify.append(
                    {
                        "case_id": case._id,
                        "update": update,
                        "close": True,
                    }
                )

            ## Assignment from Call Center ##
            # Assign Cases to Field (manually by call center)
            elif (case.date_admission >= past_42_date) and next_assignment == "fida":
                if not cati_owner_username or not fida_group:
                    continue
                update = {
                    "last_cati_user": cati_owner_username,
                    "current_assignment": "fida",
                    "next_assignment": '',
                    "owner_id": fida_group,
                    "cati_status": 'manually_assigned_to_field'
                }
                cases_to_modify.append(
                    {
                        "case_id": case._id,
                        "update": update,
                        "close": False,
                    }
                )
            # Assign cases to field (automatically)
            elif (case.date_admission >= past_42_date) and (case.date_admission < past_21_date) and (curr_assignment == "cati" or curr_assignment == "cati_tl"):
                if not cati_owner_username or not fida_group:
                    continue
                update = {
                    "last_cati_assignment": curr_assignment,
                    "last_cati_user": cati_owner_username,
                    "cati_status": 'timed_out',
                    "current_assignment": "fida",
                    "next_assignment": '',
                    "owner_id": fida_group                        
                }
                cases_to_modify.append(
                    {
                        "case_id": case._id,
                        "update": update,
                        "close": False,
                    }
                )
            # Assign Cases to Lost to Follow Up
            elif case.date_admission < past_42_date and (curr_assignment == "cati" or curr_assignment == "cati_tl"):
                if not get_owner_username(domain, curr_assignment, site_id) or not cati_owner_username:
                    continue
                update = {
                    "last_cati_assignment": curr_assignment,
                    "last_cati_user": cati_owner_username,
                    "last_user": get_owner_username(domain, curr_assignment, site_id),
                    "cati_status": 'timed_out',
                    "last_assignment": curr_assignment,
                    "current_assignment": '',
                    "closed_status": "timed_out_lost_to_follow_up",
                    "next_assignment": ''
                }
                cases_to_modify.append(
                    {
                        "case_id": case._id,
                        "update": update,
                        "close": True,
                    }
                )

            ## Assignment from Field ##
            # Assign Cases to Lost to Follow Up
            elif case.date_admission < past_42_date and (curr_assignment == "fida" or curr_assignment == "fida_tl"):
                if not get_owner_username(domain, curr_assignment, site_id):
                    continue
                update = {
                    "last_user": get_owner_username(domain, curr_assignment, site_id),
                    "last_assignment": curr_assignment,
                    "current_assignment": '',
                    "closed_status": "timed_out_lost_to_follow_up",
                    "next_assignment": '',
                }
                cases_to_modify.append(
                    {
                        "case_id": case._id,
                        "update": update,
                        "close": True,
                    }
                )
        case_blocks = [ElementTree.tostring(CaseBlock(
            create=False,
            case_id=case["case_id"],
            update=case["update"],
            close=case["close"],
            version=V2,
            ).as_xml()) for case in cases_to_modify
        ]
        submit_case_blocks(case_blocks, domain)