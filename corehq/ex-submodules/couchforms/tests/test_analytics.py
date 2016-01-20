import datetime
import uuid
from django.test import TestCase
from corehq.util.test_utils import DocTestMixin
from couchforms.analytics import domain_has_submission_in_last_30_days, \
    get_number_of_forms_per_domain, get_number_of_forms_in_domain, \
    get_first_form_submission_received, get_last_form_submission_received, \
    app_has_been_submitted_to_in_last_30_days, update_analytics_indexes, \
    get_username_in_last_form_user_id_submitted, get_all_user_ids_submitted, \
    get_all_xmlns_app_id_pairs_submitted_to_in_domain, \
    get_last_form_submission_for_user_for_app, get_number_of_submissions, get_form_analytics_metadata, \
    get_number_of_forms_of_all_types, get_number_of_forms_by_type
from couchforms.models import XFormInstance, XFormError


class CouchformsAnalyticsTest(TestCase, DocTestMixin):
    dependent_apps = ['corehq.couchapps', 'corehq.apps.domain', 'corehq.form_processor',
                      'corehq.sql_accessors']

    @classmethod
    def setUpClass(cls):
        from casexml.apps.case.tests.util import delete_all_xforms
        delete_all_xforms()
        cls.now = datetime.datetime.utcnow()
        cls._60_days = datetime.timedelta(days=60)
        cls.domain = 'my_crazy_analytics_domain'
        cls.app_id = uuid.uuid4().hex
        cls.xmlns = 'my://crazy.xmlns/'
        cls.user_id = uuid.uuid4().hex
        cls.forms = [
            XFormInstance(domain=cls.domain, received_on=cls.now,
                          app_id=cls.app_id, xmlns=cls.xmlns,
                          form={'meta': {'userID': cls.user_id, 'username': 'francis'}}),
            XFormInstance(domain=cls.domain, received_on=cls.now - cls._60_days,
                          app_id=cls.app_id, xmlns=cls.xmlns,
                          form={'meta': {'userID': cls.user_id, 'username': 'frank'}}),
        ]
        cls.error_forms = [XFormError(domain=cls.domain)]
        cls.all_forms = cls.forms + cls.error_forms
        for form in cls.all_forms:
            form.save()

        update_analytics_indexes()

    @classmethod
    def tearDownClass(cls):
        for form in cls.all_forms:
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

    def test_get_all_xmlns_app_id_pairs_submitted_to_in_domain(self):
        self.assertEqual(
            get_all_xmlns_app_id_pairs_submitted_to_in_domain(self.domain),
            {(self.xmlns, self.app_id)})

    def test_get_last_form_submission_for_user_for_app(self):
        self.assert_docs_equal(
            get_last_form_submission_for_user_for_app(self.domain, self.user_id, self.app_id),
            self.forms[0])

    def test_get_number_of_submissions(self):
        self.assertEqual(
            get_number_of_submissions(
                self.domain, self.user_id, self.xmlns, self.app_id,
                end=self.now, start=self.now - datetime.timedelta(days=100)), 2)

    def test_get_number_of_forms_of_all_types(self):
        self.assertEqual(
            get_number_of_forms_of_all_types(self.domain),
            len(self.all_forms)
        )

    def test_get_number_of_forms_by_type_xforminstance(self):
        self.assertEqual(
            get_number_of_forms_by_type(self.domain, 'XFormInstance'),
            len(self.forms)
        )

    def test_get_number_of_forms_by_type_xformerror(self):
        self.assertEqual(
            get_number_of_forms_by_type(self.domain, 'XFormError'),
            len(self.error_forms)
        )


class ExportsFormsAnalyticsTest(TestCase, DocTestMixin):
    dependent_apps = ['corehq.couchapps', 'corehq.apps.domain', 'corehq.form_processor',
                      'corehq.sql_accessors']
    maxDiff = None

    @classmethod
    def setUpClass(cls):
        from casexml.apps.case.tests.util import delete_all_xforms
        from corehq.apps.app_manager.models import Application, Module, Form
        delete_all_xforms()
        cls.domain = 'exports_forms_analytics_domain'
        cls.app_id_1 = uuid.uuid4().hex
        cls.xmlns_1 = 'my://crazy.xmlns/'
        cls.xmlns_2 = 'my://crazy.xmlns/app'
        cls.apps = [
            Application(domain=cls.domain,
                        modules=[Module(forms=[Form(xmlns=cls.xmlns_2)])])
        ]
        for app in cls.apps:
            app.save()
        cls.app_id_2 = cls.apps[0]._id
        cls.forms = [
            XFormInstance(domain=cls.domain,
                          app_id=cls.app_id_1, xmlns=cls.xmlns_1),
            XFormInstance(domain=cls.domain,
                          app_id=cls.app_id_1, xmlns=cls.xmlns_1),
            XFormInstance(domain=cls.domain,
                          app_id=cls.app_id_2, xmlns=cls.xmlns_2),
        ]
        cls.error_forms = [XFormError(domain=cls.domain)]
        cls.all_forms = cls.forms + cls.error_forms
        for form in cls.all_forms:
            form.save()

        update_analytics_indexes()

    @classmethod
    def tearDownClass(cls):
        for form in cls.all_forms:
            form.delete()
        for app in cls.apps:
            app.delete()

    def test_get_form_analytics_metadata__no_match(self):
        self.assertIsNone(
            get_form_analytics_metadata(self.domain, self.app_id_1, self.xmlns_2))

    def test_get_form_analytics_metadata__no_app(self):
        self.assertEqual(
            get_form_analytics_metadata(self.domain, self.app_id_1, self.xmlns_1),
            {'submissions': 2, 'xmlns': 'my://crazy.xmlns/'}
        )

    def test_get_form_analytics_metadata__app(self):
        self.assertEqual(get_form_analytics_metadata(self.domain, self.app_id_2, self.xmlns_2), {
            'app': {'id': self.app_id_2, 'langs': [], 'name': None},
            'app_deleted': False,
            'form': {'id': 0, 'name': {}},
            'module': {'id': 0, 'name': {}},
            'submissions': 1,
            'xmlns': 'my://crazy.xmlns/app'
        })
