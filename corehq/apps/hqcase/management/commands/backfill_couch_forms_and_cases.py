from __future__ import absolute_import
from __future__ import print_function

import json
import os

from django.core.management import BaseCommand

from corehq.apps.domain.dbaccessors import iter_domains
from corehq.apps.es import FormES, CaseES
from corehq.apps.hqcase.dbaccessors import get_all_case_owner_ids
from corehq.dbaccessors.couchapps.cases_by_server_date.by_owner_server_modified_on import \
    get_case_ids_modified_with_owner_since
from corehq.util.dates import iso_string_to_date
from corehq.util.log import with_progress_bar
from couchforms.dbaccessors import get_form_ids_by_type
from dimagi.utils.chunked import chunked


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('start')
        parser.add_argument('end')

    def handle(self, start, end, *args, **options):
        start = iso_string_to_date(start)
        end = iso_string_to_date(end)
        print("[1] Get all form ids by domain for date range")
        all_form_ids_by_domain = use_json_cache_file(
            filename='all_form_ids_received_{}_to_{}_by_domain.json'.format(start, end),
            fn=lambda: generate_all_form_ids_by_domain(start, end)
        )
        print("[2] Get form ids by domain missing from ES")
        missing_form_ids_by_domain = {}
        for domain, form_ids in all_form_ids_by_domain.items():
            missing_form_ids_by_domain[domain] = use_json_cache_file(
                filename='missing_form_ids_{}_to_{}__{}'.format(start, end, domain),
                fn=lambda: get_form_ids_missing_from_elasticsearch(form_ids)
            )
        print("[3] Get all case ids by domain for date range")
        all_case_ids_by_domain = use_json_cache_file(
            filename='all_case_ids_last_modified_{}_to_{}_by_domain.json'.format(start, end),
            fn=lambda: get_all_case_ids_by_domain(start, end)
        )
        print("[4] Get case ids by domain missing from ES")
        missing_case_ids_by_domain = {}
        for domain, case_ids in all_case_ids_by_domain.items():
            missing_case_ids_by_domain[domain] = use_json_cache_file(
                filename='missing_case_ids_{}_to_{}__{}'.format(start, end, domain),
                fn=lambda: get_case_ids_missing_from_elasticsearch(case_ids)
            )
        print({domain: case_ids[0] for domain, case_ids in missing_case_ids_by_domain.iteritems()
               if case_ids})


def generate_all_form_ids_by_domain(start, end):
    form_ids_by_domain = {
        domain: get_form_ids_by_type(domain, 'XFormInstance', start, end)
        for domain in iter_domains()
    }
    return {
        domain: form_ids
        for domain, form_ids in form_ids_by_domain.items()
        if form_ids
    }


def get_form_ids_missing_from_elasticsearch(all_form_ids):
    missing_from_elasticsearch = set()
    for form_ids in chunked(all_form_ids, 500):
        form_ids = set(form_ids)
        not_missing = set(FormES().doc_id(form_ids).get_ids())
        missing_from_elasticsearch.update(form_ids - not_missing)
        assert not_missing - form_ids == set()
    return list(missing_from_elasticsearch)


def get_case_ids_missing_from_elasticsearch(all_case_ids):
    missing_from_elasticsearch = set()
    for case_ids in chunked(all_case_ids, 500):
        case_ids = set(case_ids)
        not_missing = set(CaseES().doc_id(case_ids).get_ids())
        missing_from_elasticsearch.update(case_ids - not_missing)
        assert not_missing - case_ids == set()
    return list(missing_from_elasticsearch)


def get_all_case_ids_by_domain(start, end):
    all_case_ids_by_domain = {}
    for domain in iter_domains():
        print('Pulling cases for {}'.format(domain))
        all_case_ids_by_domain[domain] = use_json_cache_file(
            filename='all_case_ids_last_modified_{}_to_{}__{}.json'.format(start, end, domain),
            fn=lambda: get_all_case_ids_for_domain(domain, start, end)
        )
    return all_case_ids_by_domain


def get_all_case_ids_for_domain(domain, start, end):
    case_ids = []
    for owner_id in with_progress_bar(get_all_case_owner_ids(domain)):
        case_ids.extend(get_case_ids_modified_with_owner_since(domain, owner_id, start, end))
    return case_ids


def use_json_cache_file(filename, fn):
    if os.path.exists(filename):
        print("Retrieving from JSON cache file: {}".format(filename))
        with open(filename) as f:
            result = json.load(f)
    else:
        print("Generating...")
        result = fn()
        print("Writing to JSON cache file: {}".format(filename))
        try:
            with open(filename, 'w') as f:
                json.dump(result, f)
        except Exception:
            os.remove(filename)
            raise
    return result
