from collections import defaultdict
import itertools
import logging
from casexml.apps.case.models import CommCareCase
from casexml.apps.phone.caselogic import get_footprint
from casexml.apps.phone.data_providers.case.load_testing import append_update_to_response
from casexml.apps.phone.data_providers.case.stock import get_stock_payload
from casexml.apps.phone.data_providers.case.utils import get_case_sync_updates, CaseStub
from casexml.apps.phone.models import CaseState
from corehq.apps.hqcase.dbaccessors import iter_lite_cases_json, \
    get_n_case_ids_in_domain_by_owner
from corehq.util.dates import iso_string_to_datetime
from dimagi.utils.parsing import string_to_utc_datetime


logger = logging.getLogger(__name__)
