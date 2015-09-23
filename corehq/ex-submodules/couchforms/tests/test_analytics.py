import datetime
import uuid
from django.test import TestCase
from couchforms.analytics import domain_has_submission_in_last_30_days, \
    get_number_of_forms_per_domain, get_number_of_forms_in_domain, \
    get_first_form_submission_received, get_last_form_submission_received, \
    app_has_been_submitted_to_in_last_30_days, update_analytics_indexes, \
    get_username_in_last_form_user_id_submitted, get_all_user_ids_submitted
from couchforms.models import XFormInstance


class CouchformsAnalyticsTest(TestCase):

    @classmethod
    def setUpClass(cls):
        from casexml.apps.case.tests import delete_all_xforms
        delete_all_xforms()
        cls.now = datetime.datetime.utcnow()
        cls._60_days = datetime.timedelta(days=60)
        cls.domain = 'my_crazy_analytics_domain'
        cls.app_id = uuid.uuid4().hex
        cls.xmlns = 'my://crazy.xmlns/'
        cls.user_id = uuid.uuid4().hex
        cls.forms = [
            XFormInstance(domain=cls.domain, received_on=cls.now,
                          app_id=cls.app_id, xmlns=cls.xmlns, form={'meta': {'userID': cls.user_id, 'username': 'francis'}}),
            XFormInstance(domain=cls.domain, received_on=cls.now - cls._60_days,
                          app_id=cls.app_id, xmlns=cls.xmlns, form={'meta': {'userID': cls.user_id, 'username': 'frank'}}),
        ]
        for form in cls.forms:
            form.save()

        update_analytics_indexes()

    @classmethod
    def tearDownClass(cls):
        for form in cls.forms:
            form.delete()

    def test_domain_has_submission_in_last_30_days(self):
        self.assertEqual(
            domain_has_submission_in_last_30_days(self.domain), True)

    def test_get_number_of_forms_per_domain(self):
        self.assertEqual(
            get_number_of_forms_per_domain(), {self.domain: 2})

    def test_get_number_of_forms_in_domain(self):
        self.assertEqual(
            get_number_of_forms_in_domain(self.domain), 2)

    def test_get_first_form_submission_received(self):
        self.assertEqual(
            get_first_form_submission_received(self.domain),
            self.now - self._60_days)

    def test_get_last_form_submission_received(self):
        self.assertEqual(
            get_last_form_submission_received(self.domain), self.now)

    def test_app_has_been_submitted_to_in_last_30_days(self):
        self.assertEqual(
            app_has_been_submitted_to_in_last_30_days(self.domain, self.app_id),
            True)

    def test_get_username_in_last_form_user_id_submitted(self):
        self.assertEqual(
            get_username_in_last_form_user_id_submitted(self.domain, self.user_id),
            'francis')

    def test_get_all_user_ids_submitted(self):
        self.assertEqual(
            get_all_user_ids_submitted(self.domain), {self.user_id})
