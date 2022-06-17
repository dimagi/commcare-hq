from django.conf import settings
from django.test import TestCase

from corehq.form_processor.tests.test_cases import _create_case
from corehq.form_processor.tests.utils import FormProcessorTestUtils, sharded
from corehq.sql_db.tests.utils import new_id_in_different_dbalias

from .. import util
from ..const import LookupErrors

DOMAIN = 'test-case-importer-utils'


class Unexpected(Exception):
    pass


@sharded
class TestImporterUtils(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.case1 = _create_case(DOMAIN, case_id='c1', case_type='t1', external_id='123')
        cls.case2 = _create_case('d2', case_id='c2', case_type='t2', external_id='123')
        if settings.USE_PARTITIONED_DATABASE:
            cls.addClassCleanup(cls.case1.delete)
            cls.addClassCleanup(cls.case2.delete)

    @classmethod
    def tearDownClass(cls):
        if settings.USE_PARTITIONED_DATABASE:
            FormProcessorTestUtils.delete_all_sql_forms(DOMAIN)
            FormProcessorTestUtils.delete_all_sql_forms('d2')
        super().tearDownClass()

    def test_lookup_case_with_case_id(self):
        result = util.lookup_case("case_id", "c1", DOMAIN, "t1")
        self.checkResult(result, self.case1, None)

    def test_lookup_case_with_case_id_and_wrong_type(self):
        result = util.lookup_case("case_id", "c1", DOMAIN, "t2")
        self.checkResult(result, None, LookupErrors.NotFound)

    def test_lookup_case_with_unknown_case_id(self):
        result = util.lookup_case("case_id", "unknown", DOMAIN, "t2")
        self.checkResult(result, None, LookupErrors.NotFound)

    def test_lookup_case_with_external_id(self):
        result = util.lookup_case(util.EXTERNAL_ID, "123", DOMAIN, "t1")
        self.checkResult(result, self.case1, None)

    def test_lookup_case_with_external_id_and_wrong_type(self):
        result = util.lookup_case(util.EXTERNAL_ID, "123", DOMAIN, "t2")
        self.checkResult(result, None, LookupErrors.NotFound)

    def test_lookup_case_with_unknown_external_id(self):
        result = util.lookup_case(util.EXTERNAL_ID, "unknown", DOMAIN, "t1")
        self.checkResult(result, None, LookupErrors.NotFound)

    def test_lookup_case_with_multiple_results(self):
        case3_id = new_id_in_different_dbalias(self.case1.case_id)  # raises SkipTest on non-sharded db
        case3 = _create_case(DOMAIN, case_id=case3_id, case_type='t1', external_id='123')
        self.addCleanup(case3.delete)

        result = util.lookup_case(util.EXTERNAL_ID, "123", DOMAIN, "t1")
        self.checkResult(result, None, LookupErrors.MultipleResults)

    def checkResult(self, result, case, code):
        def get_case_id(case):
            return None if case is None else case.case_id
        rcase, rcode = result
        self.assertEqual((get_case_id(rcase), rcode), (get_case_id(case), code))
