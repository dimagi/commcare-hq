import uuid

from django.test import TestCase

from corehq.apps.es.tests.utils import es_test
from corehq.apps.hqcase.analytics import get_number_of_cases_in_domain
from corehq.form_processor.tests.utils import FormProcessorTestUtils
from corehq.apps.es.cases import case_adapter
from corehq.apps.es.client import manager
from corehq.apps.es.domains import domain_adapter

from corehq.util.test_utils import create_and_save_a_case
from testapps.test_pillowtop.utils import process_pillow_changes


@es_test(requires=[case_adapter, domain_adapter])
class ESAccessorsTest(TestCase):
    domain = 'hqadmin-es-accessor'

    def tearDown(self):
        FormProcessorTestUtils.delete_all_cases_forms_ledgers(self.domain)
        super(ESAccessorsTest, self).tearDown()

    def test_get_number_of_cases_in_domain(self):
        cases = [self._create_case_and_sync_to_es() for _ in range(4)]
        self.assertEqual(
            get_number_of_cases_in_domain(self.domain),
            len(cases)
        )

    def _create_case_and_sync_to_es(self):
        case_id = uuid.uuid4().hex
        case_name = 'case-name-{}'.format(uuid.uuid4().hex)
        with process_pillow_changes('case-pillow', {'skip_ucr': True}):
            with process_pillow_changes('DefaultChangeFeedPillow'):
                create_and_save_a_case(self.domain, case_id, case_name)
        manager.index_refresh(case_adapter.index_name)
        return case_id, case_name
