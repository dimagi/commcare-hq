from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import json
import os
import time

from six.moves import zip_longest
from django.core.management import BaseCommand

from corehq.apps.change_feed.topics import get_topic_for_doc_type
from corehq.apps.domain.dbaccessors import iter_domains
from corehq.apps.es import FormES, CaseES
from corehq.apps.hqcase.dbaccessors import get_all_case_owner_ids
from corehq.dbaccessors.couchapps.cases_by_server_date.by_owner_server_modified_on import \
    get_case_ids_modified_with_owner_since
from corehq.doctypemigrations.continuous_migrate import _bulk_get_revs
from corehq.util.dates import iso_string_to_date
from corehq.util.log import with_progress_bar
from couchforms.dbaccessors import get_form_ids_by_type
from couchforms.models import XFormInstance
from dimagi.utils.chunked import chunked
from pillowtop import get_pillow_by_name
from pillowtop.feed.interface import ChangeMeta
from io import open


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
                filename='missing_form_ids_{}_to_{}__{}.json'.format(start, end, domain),
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
            if case_ids:
                missing_case_ids_by_domain[domain] = use_json_cache_file(
                    filename='missing_case_ids_{}_to_{}__{}.json'.format(start, end, domain),
                    fn=lambda: get_case_ids_missing_from_elasticsearch(case_ids)
                )

        print("[5] Get all the _revs for these docs")
        case_metadata = use_json_cache_file(
            filename='missing_case_metadata_{}_to_{}.json'.format(start, end),
            fn=lambda: prepare_metadata(missing_case_ids_by_domain)
        )
        form_metadata = use_json_cache_file(
            filename='missing_form_metadata_{}_to_{}.json'.format(start, end),
            fn=lambda: prepare_metadata(missing_form_ids_by_domain)
        )

        print("[6] Publish changes for docs missing from ES!")
        interleaved_changes = (change for pair in zip_longest(
            iter_case_changes(case_metadata),
            iter_form_changes(form_metadata),
        ) for change in pair if change is not None)
        for changes in chunked(interleaved_changes, 100):
            for change in changes:
                publish_change(change)
            time.sleep(1)


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


def prepare_metadata(doc_ids_by_domain):
    domain_id_rev_list = []
    for domain, all_doc_ids in doc_ids_by_domain.items():
        for doc_ids in chunked(all_doc_ids, 500):
            doc_id_rev_list = _bulk_get_revs(XFormInstance.get_db(), doc_ids)
            assert len(doc_id_rev_list) == len(doc_ids)
            domain_id_rev_list.extend([[domain, doc_id, doc_rev]
                                       for doc_id, doc_rev in doc_id_rev_list])
    return domain_id_rev_list


PROCESSOR, = get_pillow_by_name('DefaultChangeFeedPillow').processors
PRODUCER = PROCESSOR._producer
DATA_SOURCE_TYPE = PROCESSOR._data_source_type
DATA_SOURCE_NAME = PROCESSOR._data_source_name


def iter_case_changes(case_metadata):
    for domain, doc_id, doc_rev in case_metadata:
        yield create_case_change_meta(domain, doc_id, doc_rev)


def iter_form_changes(form_metadata):
    for domain, doc_id, doc_rev in form_metadata:
        yield create_form_change_meta(domain, doc_id, doc_rev)


def create_case_change_meta(domain, doc_id, doc_rev):
    return create_change_meta('CommCareCase', domain, doc_id, doc_rev)


def create_form_change_meta(domain, doc_id, doc_rev):
    return create_change_meta('XFormInstance', domain, doc_id, doc_rev)


def create_change_meta(doc_type, domain, doc_id, doc_rev):
    return ChangeMeta(
        document_id=doc_id,
        document_rev=doc_rev,
        data_source_type=DATA_SOURCE_TYPE,
        data_source_name=DATA_SOURCE_NAME,
        document_type=doc_type,
        document_subtype=None,  # should be case.type or form.xmlns, but not used anywhere
        domain=domain,
        is_deletion=False,
    )


def publish_change(change_meta):
    topic = get_topic_for_doc_type(change_meta.document_type, DATA_SOURCE_TYPE)
    print(topic, change_meta)
    PRODUCER.send_change(topic, change_meta)
