from __future__ import absolute_import
from __future__ import unicode_literals
import six
from collections import Counter

from corehq.apps.es import CaseSearchES
from corehq.apps.es.aggregations import Aggregation, AggregationResult
from corehq.apps.users.models import CommCareUser
from corehq.form_processor.backends.sql.dbaccessors import CaseAccessorSQL
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from dimagi.utils.couch.database import iter_docs

from .case_utils import CASE_TYPE_VOUCHER, CASE_TYPE_PERSON
from .const import VOUCHER_ID, ENIKSHAY_ID


class DuplicateIdsResult(AggregationResult):

    def iter_case_ids(self):
        for bucket in self.raw['duplicate_ids']['readable_ids']['values']['buckets']:
            # Note: bucket['doc_count'] exists, and bucket['key'] is the readable ID
            for doc in bucket['case_ids']['hits']['hits']:
                yield doc['_id']


class DuplicateIdsAggregation(Aggregation):
    type = 'duplicate_ids'
    name = 'duplicate_ids'
    result_class = DuplicateIdsResult

    def __init__(self, id_property):
        self.body = {
            "nested": {
                "path": "case_properties"
            },
            "aggs": {
                "readable_ids": {
                    "filter": {
                        "term": {
                            "case_properties.key": id_property
                        }
                    },
                    "aggs": {
                        "values": {
                            "terms": {
                                "field": "case_properties.value",
                                "size": 100000,
                                "min_doc_count": 2
                            },
                            "aggs": {
                                "case_ids": {
                                    "top_hits": {
                                        "_source": False,
                                        "size": 100
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }

    def assemble(self):
        return self.body


def get_case_ids_with_duplicates(domain, case_type):
    id_property = {'voucher': VOUCHER_ID, 'person': ENIKSHAY_ID}[case_type]
    res = (CaseSearchES()
           .case_type('voucher')
           .domain(domain)
           .aggregations([DuplicateIdsAggregation(id_property)])
           .size(0)
           .run())
    return list(res.aggregations.duplicate_ids.iter_case_ids())


def get_cases_with_duplicate_ids(domain, case_type, all_case_ids):
    accessor = CaseAccessors(domain)
    id_property = {'voucher': VOUCHER_ID, 'person': ENIKSHAY_ID}[case_type]
    all_cases = [
        {
            'case_id': case.case_id,
            'readable_id': case.get_case_property(id_property),
            'opened_on': case.opened_on,
        }
        for case in accessor.iter_cases(all_case_ids)
    ]
    counts = Counter(case['readable_id'] for case in all_cases)
    return [case for case in all_cases if counts[case['readable_id']] > 1]


def get_bad_case_info(domain, case_type, full_debug_info=False):
    accessor = CaseAccessors(domain)
    case_ids = accessor.get_case_ids_in_domain(case_type)
    bad_cases = get_cases_with_duplicate_ids(domain, case_type, case_ids)
    add_debug_info_to_cases(bad_cases, full_debug_info)
    context = {
        'case_type': case_type,
        'num_bad_cases': len(bad_cases),
        'num_total_cases': len(case_ids),
        'num_good_cases': len(case_ids) - len(bad_cases),
        'bad_cases': sorted(bad_cases, key=lambda case: case['opened_on'], reverse=True)
    }
    return context


def add_debug_info_to_cases(bad_cases, full_debug_info):
    _add_form_info_to_cases(bad_cases, full_debug_info)
    _add_user_info_to_cases(bad_cases)


def _add_form_info_to_cases(bad_cases, full_debug_info):
    for case in bad_cases[:None if full_debug_info else 300]:
        form = CaseAccessorSQL.get_transactions(case['case_id'])[0].form
        if form:
            case['form_name'] = form.form_data.get('@name', 'NA')
            form_device_number = form.form_data.get('serial_id', {}).get('outputs', {}).get('device_number')
            case['device_number_in_form'] = form_device_number
            case['form_device_id'] = form.metadata.deviceID
            case['form_user_id'] = form.user_id
            case['auth_user_id'] = form.auth_context.get('user_id')


def _add_user_info_to_cases(bad_cases):
    user_info = _get_user_info(
        case['form_user_id'] for case in bad_cases if 'form_user_id' in case)

    auth_user_ids = [case['auth_user_id'] for case in bad_cases
                        if 'auth_user_id' in case]
    auth_usernames = {user_doc['_id']: user_doc['username'] for user_doc in
                      iter_docs(CommCareUser.get_db(), auth_user_ids)}
    for case in bad_cases:
        user_dict = user_info.get(case.get('form_user_id'))
        if user_dict:
            case['username'] = user_dict['username']
            device_id = case['form_device_id']
            if device_id == 'Formplayer':
                if case['form_user_id'] == case['auth_user_id']:
                    device_id = "WebAppsLogin"
                else:
                    auth_username = auth_usernames.get(case['auth_user_id'])
                    device_id = "WebAppsLogin*{}*as*{}".format(
                        auth_username, user_dict['username']).replace('.', '_')
            try:
                device_number = user_dict['device_ids'].index(device_id) + 1
            except ValueError:
                device_number = -1
            case['real_device_number'] = six.text_type(device_number)


def _get_user_info(user_ids):
    return {
        user_doc['_id']: {
            'username': user_doc['username'].split('@')[0],
            'device_ids': [d['device_id'] for d in user_doc['devices']],
        }
        for user_doc in iter_docs(CommCareUser.get_db(), user_ids)
    }
