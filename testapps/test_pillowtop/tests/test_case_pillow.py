import uuid
from unittest.mock import patch

from django.test import TestCase

from pillow_retry.models import PillowError

from corehq.apps.case_search.models import CaseSearchConfig
from corehq.apps.es import CaseES, CaseSearchES
from corehq.apps.es.case_search import case_search_adapter
from corehq.apps.es.cases import case_adapter
from corehq.apps.es.client import manager
from corehq.apps.es.tests.utils import es_test
from corehq.form_processor.models import CommCareCase
from corehq.form_processor.tests.utils import (
    FormProcessorTestUtils,
    create_case,
)
from testapps.test_pillowtop.utils import process_pillow_changes


@es_test(requires=[case_adapter, case_search_adapter])
class CasePillowTest(TestCase):
    domain = 'case-pillowtest-domain'

    @classmethod
    def setUpClass(cls):
        super(CasePillowTest, cls).setUpClass()
        # enable case search for this domain
        CaseSearchConfig.objects.create(domain=cls.domain, enabled=True)

    def setUp(self):
        super(CasePillowTest, self).setUp()
        self.process_case_changes = process_pillow_changes('DefaultChangeFeedPillow')
        self.process_case_changes.add_pillow('case-pillow', {'skip_ucr': True})
        FormProcessorTestUtils.delete_all_cases()

    def tearDown(self):
        FormProcessorTestUtils.delete_all_cases_forms_ledgers(self.domain)
        PillowError.objects.all().delete()
        super(CasePillowTest, self).tearDown()

    def test_case_pillow(self):
        case_id, case_name = self._create_case_and_sync_to_es()

        # confirm change made it to elasticserach
        results = CaseES().run()
        self.assertEqual(1, results.total)
        case_doc = results.hits[0]
        self.assertEqual(self.domain, case_doc['domain'])
        self.assertEqual(case_id, case_doc['_id'])
        self.assertEqual(case_name, case_doc['name'])

    def test_case_pillow_error_in_case_es(self):
        self.assertEqual(0, PillowError.objects.filter(pillow='case-pillow').count())
        with (
            patch.object(case_adapter, 'from_python') as case_transform,
            patch.object(case_search_adapter, 'from_python') as case_search_transform,
        ):
            case_transform.side_effect = Exception('case_transform error')
            case_search_transform.side_effect = Exception('case_search_transform error')
            case_id, case_name = self._create_case_and_sync_to_es()

        # confirm change did not make it to case search index
        results = CaseSearchES().run()
        self.assertEqual(0, results.total)

        # confirm change did not make it to case index
        results = CaseES().run()
        self.assertEqual(0, results.total)

        self.assertEqual(1, PillowError.objects.filter(pillow='case-pillow').count())

    def test_case_soft_deletion(self):
        case_id, case_name = self._create_case_and_sync_to_es()

        # verify there
        results = CaseES().run()
        self.assertEqual(1, results.total)
        search_results = CaseSearchES().run()
        self.assertEqual(1, search_results.total)

        # soft delete the case
        with self.process_case_changes:
            CommCareCase.objects.soft_delete_cases(self.domain, [case_id])
        manager.index_refresh(case_adapter.index_name)
        manager.index_refresh(case_search_adapter.index_name)

        # ensure not there anymore
        results = CaseES().run()
        self.assertEqual(0, results.total)
        search_results = CaseSearchES().run()
        self.assertEqual(0, search_results.total)

    def test_case_hard_deletion(self):
        case_id, case_name = self._create_case_and_sync_to_es()

        # verify there
        results = CaseES().run()
        self.assertEqual(1, results.total)
        search_results = CaseSearchES().run()
        self.assertEqual(1, search_results.total)

        # hard delete the case
        with self.process_case_changes:
            CommCareCase.objects.hard_delete_cases(self.domain, [case_id])
        manager.index_refresh(case_adapter.index_name)
        manager.index_refresh(case_search_adapter.index_name)
        # ensure not there anymore
        results = CaseES().run()
        self.assertEqual(0, results.total)
        search_results = CaseSearchES().run()
        self.assertEqual(0, search_results.total)

    def _create_case_and_sync_to_es(self):
        case_id = uuid.uuid4().hex
        case_name = 'case-name-{}'.format(uuid.uuid4().hex)
        with self.process_case_changes:
            create_case(self.domain, case_id=case_id, name=case_name, save=True, enable_kafka=True)
        manager.index_refresh(case_adapter.index_name)
        manager.index_refresh(case_search_adapter.index_name)
        return case_id, case_name
