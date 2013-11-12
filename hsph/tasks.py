import datetime, pytz

from celery.task import periodic_task
from celery.schedules import crontab
from django.conf import settings
from xml.etree import ElementTree

from casexml.apps.case.models import CommCareCase
from casexml.apps.case.mock import CaseBlock
from casexml.apps.case.xml import V2
from corehq.apps.domain.models import Domain
from corehq.apps.hqcase.utils import submit_case_blocks


DOMAINS = ["hsph-dev", "hsph-betterbirth"]
PAST_N_DAYS = 21
GROUPS_TO_CHECK = ["cati", "cati-tl"]
GROUP_SHOULD_BE = "fida"


@periodic_task(
    run_every=crontab(minute=1, hour=0),
    queue=getattr(settings, 'CELERY_PERIODIC_QUEUE', 'celery')
)
def update_case_properties():
	"""
	Everyday one-minute after UTC (5:31am India Time), checks for "birth" cases with date_admission 
	past 21 days and assigned_to property as one of GROUPS_TO_CHECK, and if there are such
	cases their assigned_to property is set to GROUP_SHOULD_BE
	"""
	time_zone = Domain.get_by_name(DOMAINS[0]).default_timezone
	time_zone = pytz.timezone(time_zone)
	past_n_date = datetime.datetime.now(time_zone) - datetime.timedelta(PAST_N_DAYS)
	for domain in DOMAINS:
		case_list = CommCareCase.view("hqcase/types_by_domain", key=[domain, "birth"], include_docs=True, reduce=False)
		case_list = case_list.all()
		cases_to_modify = []
		for case in case_list:
			if (hasattr(case, "assigned_to") and
			    hasattr(case, "date_admission") and
			    case.date_admission < past_n_date.date() and
			    case.assigned_to in GROUPS_TO_CHECK):
					case.assigned_to = GROUP_SHOULD_BE
					cases_to_modify.append(case)
		case_blocks = [ElementTree.tostring(CaseBlock(
			create = False,
			case_id = c._id,
			update = {"assigned_to": c.assigned_to},
			version = V2,
			).as_xml()) for c in cases_to_modify
		]
		submit_case_blocks(case_blocks, domain)