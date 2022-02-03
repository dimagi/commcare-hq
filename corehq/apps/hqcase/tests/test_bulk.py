import uuid
from unittest import mock

from django.test import TestCase

from casexml.apps.case.mock import CaseBlock

from corehq.apps.hqcase.bulk import CaseBulkDB
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.form_processor.models import XFormInstance
from corehq.form_processor.tests.utils import FormProcessorTestUtils


@mock.patch('corehq.apps.hqcase.bulk.CASEBLOCK_CHUNKSIZE', new=5)
class TestUpdateCases(TestCase):
    domain = 'test_bulk_update_cases'

    def tearDown(self):
        FormProcessorTestUtils.delete_all_xforms()
        FormProcessorTestUtils.delete_all_cases()
        super().tearDown()

    def test(self):
        with CaseBulkDB(self.domain, 'my_user_id', 'my_device_id') as bulk_db:
            for i in range(1, 18):
                bulk_db.save(CaseBlock(
                    create=True,
                    case_id=str(uuid.uuid4()),
                    case_type='patient',
                    case_name=f"case_{i}",
                    update={'phase': '1'},
                ))

        self.assertEqual(len(XFormInstance.objects.get_form_ids_in_domain(self.domain)), 4)
        case_accessor = CaseAccessors(self.domain)
        self.assertEqual(len(case_accessor.get_case_ids_in_domain()), 17)
