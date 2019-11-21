import datetime
import time

from django.core.management.base import BaseCommand
from corehq.apps.userreports.tasks import _get_config_by_id, _build_indicators
from corehq.apps.change_feed.data_sources import get_document_store_for_doc_type
from custom.icds_reports.models.aggregate import CcsRecordMonthly
from pillowtop.dao.couch import ID_CHUNK_SIZE


class Command(BaseCommand):
    help = "Rebuild open ccs record cases and their corresponding person cases "

    def get_asdfsd(self, indicator_config_id, case_type_of_xmlns):
        config = _get_config_by_id(indicator_config_id)
        document_store = get_document_store_for_doc_type(
            config.domain, config.referenced_doc_type,
            case_type_or_xmlns=case_type_of_xmlns,
            load_source="build_ccs_record_ucr",
        )
        return config, document_store

    def handle(self):
        ccs_record_config, ccs_record_document_store = self.get_asdfsd('static-ccs_record_cases', 'ccs_record')
        person_config, person_document_store = self.get_asdfsd('static-person_cases_v3', 'person')

        current_month_start = datetime.date.today().replace(day=1)
        last_month_start = (current_month_start - datetime.timedelta(days=1)).replace(day=1)

        current_month_start = current_month_start.strftime('%Y-%m-%d')
        last_month_start = last_month_start.strftime('%Y-%m-%d')
        current_month_doc_ids = CcsRecordMonthly.objects.filter(open_in_month=1,
                                                                month=current_month_start).values('case_id', 'person_case_id')
        docs_last_month = CcsRecordMonthly.objects.filter(open_in_month=1,
                                                          month=last_month_start).values('case_id', 'person_case_id')

        doc_ids = current_month_doc_ids + docs_last_month

        ccs_record_doc_ids = {doc_id['case_id'] for doc_id in doc_ids}
        person_case_doc_ids = {doc_id['person_case_id'] for doc_id in doc_ids}

        self.build_indicator(ccs_record_doc_ids, ccs_record_config, ccs_record_document_store)
        self.build_indicator(person_case_doc_ids, person_config, person_document_store)

    def build_indicator(self, doc_ids, config, document_store):
        config.asynchronous = True #build through async queue
        relevant_ids = list()
        next_event = time.time() + 10
        for doc_id in doc_ids:
            relevant_ids.append(doc_id)
            if len(relevant_ids) >= ID_CHUNK_SIZE:
                _build_indicators(config, document_store, relevant_ids)
                relevant_ids = []

            if time.time() > next_event:
                print("processed till case %s" % (doc_id['case_id']))
                next_event = time.time() + 10

        if relevant_ids:
            _build_indicators(config, document_store, relevant_ids)
