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


DOMAINS = ["hsph-dev", "hsph-betterbirth"]
PAST_N_DAYS = 21
GROUPS_TO_CHECK = ["cati", "cati-tl"]
GROUP_SHOULD_BE = "fida"
TYPE = "birth"
OWNER_FIELD_MAPPINGS = {
        "cati": "cati_assignment",
        "fida": "field_follow_up_assignment"
    }
INDEXED_FIXTURES = {domain: FixtureDataItem.get_indexed_items(domain, "site", "site_id") for domain in DOMAINS}

INDEXED_GROUPS = {domain: {} for domain in DOMAINS}

# indexes groups by custom_data_key 'main_user' for easy lookups
# assumes:
#   all case_sharing groups has the key "main_user"
#   no group has same 'main_user'
def update_groups_index(domain):
    groups = Group.by_domain(domain)
    for group in groups:
        if group.case_sharing:
            INDEXED_GROUPS[domain][group.metadata["main_user"]] = group

def get_owner_username(domain, owner_type, site_id):
    if not owner_type:
        return ''
    field_name = OWNER_FIELD_MAPPINGS[owner_type]
    return INDEXED_FIXTURES[domain][site_id][field_name]

def get_group_id(domain, owner_type, site_id):
    owner_username = get_owner_username(domain, owner_type, site_id)
    return INDEXED_GROUPS[domain][owner_username]._id



def update_case_properties():
    """
    Everyday one-minute after UTC (5:31am India Time), checks for "birth" cases with date_admission 
    past 21 days and assigned_to property as one of GROUPS_TO_CHECK, and if there are such
    cases their assigned_to property is set to GROUP_SHOULD_BE
    """
    # skip if hsph doesn't exist on this server
    _domain = Domain.get_by_name(DOMAINS[0])
    if _domain is None:
        return
    time_zone = _domain.default_timezone
    time_zone = pytz.timezone(time_zone)
    past_n_date = (datetime.datetime.now(time_zone) - datetime.timedelta(PAST_N_DAYS)).date()
    for domain in DOMAINS:
        update_groups_index(domain)
        case_list = get_cases_in_domain(domain, type=TYPE)
        case_ids_to_modify = []
        for case in case_list:
            if (hasattr(case, "assigned_to") and
                hasattr(case, "date_admission") and
                case.date_admission < past_n_date and
                case.assigned_to in GROUPS_TO_CHECK):
                    case_ids_to_modify.append(case._id)
        case_blocks = [ElementTree.tostring(CaseBlock(
            create = False,
            case_id = c,
            update = {"assigned_to": GROUP_SHOULD_BE},
            version = V2,
            ).as_xml()) for c in case_ids_to_modify
        ]
        submit_case_blocks(case_blocks, domain)

past_x_date = lambda time_zone, past_x_days: (datetime.datetime.now(time_zone) - datetime.timedelta(past_x_days)).date()
get_none_or_value = lambda _object, _attribute: getattr(_object, _attribute) if (hasattr(_object, _attribute)) else ''

@periodic_task(
    run_every=crontab(minute=1, hour=0),
    queue=getattr(settings, 'CELERY_PERIODIC_QUEUE', 'celery')
)
def new_update_case_properties():
    try:
        _domain = Domain.get_by_name(DOMAINS[0])
        if _domain is None:
            return
        time_zone = _domain.default_timezone
        time_zone = pytz.timezone(time_zone)
        past_21_date = past_x_date(time_zone, 21)
        past_42_date = past_x_date(time_zone, 42)
        for domain in DOMAINS:
            case_list = get_cases_in_domain(domain, type=TYPE)
            cases_to_modify = []
            for case in case_list:
                if (not get_none_or_value(case, "owner_id") or not get_none_or_value(case, "date_admission") or not get_none_or_value(case, "site_id")):
                    continue
                curr_assignment = get_none_or_value(case, "current_assignment")
                next_assignment = get_none_or_value(case, "next_assignment")
                site_id = case.site_id
                if case.date_admission >= past_21_date and ((curr_assignment is None) and (next_assignment is None)):
                    owner_id = get_group_id(domain, "cati", site_id)
                    update = {
                        "owner_id": owner_id,
                        "current_assignment": "cati"
                    }
                    cases_to_modify.append({
                        "case_id": case._id,
                        "update": update,
                        "close": False,
                        "case": case
                    })
                elif case.date_admission < past_42_date:
                    update = {
                        "last_user": get_owner_username(domain, curr_assignment, site_id),
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
                        "case": case
                        }
                    )
                elif (case.date_admission >= past_42_date and next_assignment is "fida"):
                    update = {
                        "last_cati_assignment": curr_assignment,
                        "last_cati_user": get_owner_username(domain, "cati", site_id),
                        "current_assignment": "fida",
                        "next_assignment": '',
                        "owner_id": get_group_id(domain, "fida", site_id)
                    }
                    if ((case.date_admission < past_21_date) and (curr_assignment is "cati" or curr_assignment is "cati_tl")):
                        update.update({"cati_timed_out": "yes"})
                    cases_to_modify(
                        {
                            "case_id": case._id,
                            "update": update,
                            "close": False,
                        "case": case
                        }
                    )
            return cases_to_modify
    except Exception as e:
        print e
        import pdb; pdb.set_trace()
        # case_blocks = [ElementTree.tostring(CaseBlock(
        #     create = False,
        #     case_id = case["case_id"],
        #     update = case["update"],
        #     close = case["close"],
        #     version = V2,
        #     ).as_xml()) for case in cases_to_modify
        # ]
        # submit_case_blocks(case_blocks, domain)