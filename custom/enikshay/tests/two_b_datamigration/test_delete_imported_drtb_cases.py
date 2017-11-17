from __future__ import absolute_import
import datetime

from django.core.management import call_command
from django.test import TestCase
from elasticsearch import ConnectionError

from casexml.apps.case.mock import CaseFactory
from corehq.apps.domain.models import Domain
from corehq.apps.es import CaseSearchES
from corehq.elastic import get_es_new, send_to_elasticsearch
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.pillows.case_search import transform_case_for_elasticsearch
from corehq.pillows.mappings.case_search_mapping import CASE_SEARCH_INDEX, CASE_SEARCH_INDEX_INFO, \
    CASE_SEARCH_ALIAS
from corehq.util.elastic import ensure_index_deleted
from corehq.util.test_utils import trap_extra_setup
from custom.enikshay.tests.two_b_datamigration.test_logging import ImportDRTBTestMixin
from pillowtop.es_utils import initialize_index_and_mapping

IMPORT_ROWS = [
    # A minimal valid row
    ["1", None, None, None, "XX-XXX-0-X-00-00001", None, None, datetime.date(2017, 1, 1), "John Doe", None,
     50, "123 fake st", "91-123-456-7890"] + ([None] * 9) + ["some district", None, None, "some phi"],
    ["2", None, None, None, "XX-XXX-0-X-00-00002", None, None, datetime.date(2017, 1, 1), "Jane Doe", None,
     50, "123 fake st", "91-123-456-7890"] + ([None] * 9) + ["some district", None, None, "some phi"],
]


class TestDeleteCommand(TestCase, ImportDRTBTestMixin):

    @classmethod
    def setUpClass(cls):
        cls.project = Domain(name=cls.domain)
        cls.project.save()

        with trap_extra_setup(ConnectionError):
            ensure_index_deleted(CASE_SEARCH_INDEX)
        cls.es_client = get_es_new()

        initialize_index_and_mapping(cls.es_client, CASE_SEARCH_INDEX_INFO)

    @classmethod
    def tearDownClass(cls):
        ensure_index_deleted(CASE_SEARCH_INDEX)
        cls.project.delete()

    def _refersh_es(self, all_case_ids):
        for case in CaseAccessors(self.domain).get_cases(all_case_ids):
            send_to_elasticsearch(CASE_SEARCH_ALIAS, transform_case_for_elasticsearch(case.to_json()))
        self.es_client.indices.refresh(CASE_SEARCH_INDEX_INFO.index)

    def test_delete(self):

            case_query = CaseSearchES().domain(self.domain).doc_type("CommCareCase")

            # Import some cases
            all_case_ids = []
            with self.drtb_import(IMPORT_ROWS, "mumbai", commit=True) as (_, result_rows):
                for row in result_rows:
                    case_ids = row.get("case_ids", "")
                    self.assertTrue(
                        case_ids, "No case ids, got this error instead: {}".format(row.get("exception")))
                    all_case_ids.extend([x for x in case_ids.split(",") if x])

            # Create a case unrelated to this import
            case = CaseFactory(self.domain).create_case(
                case_type="person",
                update={
                    "created_by_migration": "bar"
                }
            )
            all_case_ids.append(case._id)

            # Send cases to ES
            self._refersh_es(all_case_ids)

            # Confirm that cases are in ES
            # 30 cases per person = 25 resistance + 1 drtb + 1 sdps + 1 person + 1 episode + 1 occurrence
            self.assertEqual(case_query.count(), (2 * 30) + 1)

            # Run the deletion script
            call_command('delete_imported_drtb_cases', self.domain, "foo", "--commit")

            # Confirm that the cases have been deleted
            self._refersh_es(all_case_ids)

            self.es_client.indices.refresh(CASE_SEARCH_INDEX_INFO.index)
            self.assertEqual(case_query.count(), 1)
