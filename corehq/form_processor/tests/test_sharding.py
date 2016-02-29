from uuid import uuid4

from django.conf import settings
from django.test import TestCase
from unittest import skipUnless

from corehq.form_processor.models import XFormInstanceSQL, CommCareCaseSQL
from corehq.form_processor.tests import create_form_for_test, FormProcessorTestUtils
from corehq.sql_db.config import PartitionConfig
from crispy_forms.tests.utils import override_settings

DOMAIN = 'sharding-test'


@override_settings(ALLOW_FORM_PROCESSING_QUERIES=True)
@skipUnless(settings.USE_PARTITIONED_DATABASE, 'Only applicable if sharding is setup')
class ShardingTests(TestCase):
    dependent_apps = ['corehq.sql_accessors', 'corehq.sql_proxy_accessors']

    @classmethod
    def setUpClass(cls):
        cls.partion_config = PartitionConfig()
        assert len(cls.partion_config.get_form_processing_dbs()) > 1

    def tearDown(self):
        FormProcessorTestUtils.delete_all_sql_forms(DOMAIN)
        FormProcessorTestUtils.delete_all_sql_cases(DOMAIN)

    def test_objects_only_in_one_db(self):
        case_id = uuid4().hex
        form = create_form_for_test(DOMAIN, case_id=case_id)

        dbs_with_form = []
        dbs_with_case = []
        for db in self.partion_config.get_form_processing_dbs():
            form_in_db = XFormInstanceSQL.objects.using(db).filter(form_id=form.form_id).exists()
            if form_in_db:
                dbs_with_form.append(db)

            case_in_db = CommCareCaseSQL.objects.using(db).filter(case_id=case_id).exists()
            if case_in_db:
                dbs_with_case.append(db)

        self.assertEqual(1, len(dbs_with_form))
        self.assertEqual(1, len(dbs_with_case))

    def test_objects_distributed_to_all_dbs(self):
        """
        Rudimentary test to ensure that not all cases / forms get saved to the same DB.
        """
        num_forms = 20
        for i in range(num_forms):
            create_form_for_test(DOMAIN, case_id=uuid4().hex)

        forms_per_db = {}
        cases_per_db = {}
        for db in self.partion_config.get_form_processing_dbs():
            forms_per_db[db] = XFormInstanceSQL.objects.using(db).filter(domain=DOMAIN).count()
            cases_per_db[db] = CommCareCaseSQL.objects.using(db).filter(domain=DOMAIN).count()

        self.assertEqual(num_forms, sum(forms_per_db.values()), forms_per_db)
        self.assertEqual(num_forms, sum(cases_per_db.values()), cases_per_db)
        self.assertTrue(
            all(num_forms_in_db < num_forms for num_forms_in_db in forms_per_db.values()),
            forms_per_db
        )
        self.assertTrue(
            all(num_cases_in_db < num_forms for num_cases_in_db in cases_per_db.values()),
            cases_per_db
        )
