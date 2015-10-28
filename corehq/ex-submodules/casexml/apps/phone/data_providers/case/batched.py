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


def filter_cases_modified_elsewhere_since_sync(cases, last_sync_token):
    """
    This function takes in a list of unwrapped case dicts and a last_sync token and
    returns the set of cases that should be applicable to be sent down on top of that
    sync token.

    This includes:

      1. All cases that were modified since the last sync date by any phone other
         than the phone that is associated with the sync token.
      2. All cases that were not on the phone at the time of last sync that are
         now on the phone.
    """
    # todo: this function is pretty ugly and is heavily optimized to reduce the number
    # of queries to couch.
    if not last_sync_token:
        return cases
    else:
        # we can start by filtering out our base set of cases to check for only
        # things that have been modified since we last synced
        def _is_relevant(case_or_case_state_dict):
            if case_or_case_state_dict:
                # only case-like things have this.
                if 'server_modified_on' in case_or_case_state_dict:
                    return string_to_utc_datetime(case['server_modified_on']) >= last_sync_token.date
            # for case states default to always checking for recent updates
            return True

        recently_modified_case_ids = [case['_id'] for case in cases if _is_relevant(case)]
        # create a mapping of all cases to sync logs for all cases that were modified
        # in the appropriate ranges.
        # todo: this should really have a better way to filter out updates from sync logs
        # that we already have in a better way.
        # todo: if this recently modified case list is huge i'm guessing this query is
        # pretty expensive
        case_log_map = CommCareCase.get_db().view(
            'phone/cases_to_sync_logs',
            keys=recently_modified_case_ids,
            reduce=False,
        )

        unique_combinations = set((row['key'], row['value']) for row in case_log_map)

        # todo: and this one is also going to be very bad. see note above about how we might
        # be able to reduce it - by finding a way to only query for sync tokens that are more
        # likely to be relevant.
        modification_dates = CommCareCase.get_db().view(
            'phone/case_modification_status',
            keys=[list(combo) for combo in unique_combinations],
            reduce=True,
            group=True,
        )
        # we'll build a structure that looks like this for efficiency:
        # { case_id: [{'token': 'token value', 'date': 'date value'}, ...]}
        all_case_updates_by_sync_token = defaultdict(list)
        for row in modification_dates:
            # format from couch is a list of objects that look like this:
            # {
            #   'value': '2012-08-22T08:55:14Z', (most recent date updated)
            #   'key': ['case-id', 'sync-token-id']
            # }
            if row['value']:
                modification_date = iso_string_to_datetime(row['value'])
                if modification_date >= last_sync_token.date:
                    case_id, sync_token_id = row['key']
                    all_case_updates_by_sync_token[case_id].append(
                        {'token': sync_token_id, 'date': modification_date}
                    )

        def case_modified_elsewhere_since_sync(case_id):
            # NOTE: uses closures
            return any([row['date'] >= last_sync_token.date and row['token'] != last_sync_token._id
                        for row in all_case_updates_by_sync_token[case_id]])

        def relevant(case):
            case_id = case['_id']
            return (case_modified_elsewhere_since_sync(case_id)
                    or not last_sync_token.phone_is_holding_case(case_id))

        return filter(relevant, cases)
