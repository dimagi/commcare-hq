import datetime
import uuid
from django.test import TestCase
from requests import ConnectionError

from corehq.elastic import get_es_new, send_to_elasticsearch
from corehq.pillows.mappings.xform_mapping import XFORM_INDEX_INFO
from corehq.util.elastic import ensure_index_deleted
from corehq.util.test_utils import DocTestMixin, trap_extra_setup
from couchforms.analytics import (
    domain_has_submission_in_last_30_days,
    get_number_of_forms_per_domain, get_number_of_forms_in_domain,
    get_first_form_submission_received, get_last_form_submission_received,
    app_has_been_submitted_to_in_last_30_days, update_analytics_indexes,
    get_all_xmlns_app_id_pairs_submitted_to_in_domain,
    get_form_analytics_metadata, get_exports_by_form,
)
from couchforms.models import XFormInstance, XFormError
from pillowtop.es_utils import initialize_index_and_mapping


class CouchformsAnalyticsTest(TestCase, DocTestMixin):

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

    def test_get_all_xmlns_app_id_pairs_submitted_to_in_domain(self):
        self.assertEqual(
            get_all_xmlns_app_id_pairs_submitted_to_in_domain(self.domain),
            {(self.xmlns, self.app_id)})


class ExportsFormsAnalyticsTest(TestCase, DocTestMixin):
    maxDiff = None

    @classmethod
    def setUpClass(cls):
        from casexml.apps.case.tests.util import delete_all_xforms
        from corehq.apps.app_manager.models import Application, Module, Form
        delete_all_xforms()

        with trap_extra_setup(ConnectionError, msg="cannot connect to elasicsearch"):
            cls.es = get_es_new()
            initialize_index_and_mapping(cls.es, XFORM_INDEX_INFO)

        cls.domain = 'exports_forms_analytics_domain'
        cls.app_id_1 = 'a' + uuid.uuid4().hex
        cls.app_id_2 = 'b' + uuid.uuid4().hex
        cls.xmlns_1 = 'my://crazy.xmlns/'
        cls.xmlns_2 = 'my://crazy.xmlns/app'
        cls.apps = [
            Application(_id=cls.app_id_2, domain=cls.domain,
                        modules=[Module(forms=[Form(xmlns=cls.xmlns_2)])])
        ]
        for app in cls.apps:
            app.save()
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
            send_to_elasticsearch('forms', form.to_json())

        cls.es.indices.refresh(XFORM_INDEX_INFO.index)
        update_analytics_indexes()

    @classmethod
    def tearDownClass(cls):
        for form in cls.all_forms:
            form.delete()
        for app in cls.apps:
            app.delete()
        ensure_index_deleted(XFORM_INDEX_INFO.index)

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

    def test_get_exports_by_form(self):
        self.assertEqual(get_exports_by_form(self.domain), [{
            'value': {'xmlns': 'my://crazy.xmlns/', 'submissions': 2},
            'key': ['exports_forms_analytics_domain', self.app_id_1,
                    'my://crazy.xmlns/']
        }, {
            'value': {
                'xmlns': 'my://crazy.xmlns/app',
                'form': {'name': {}, 'id': 0},
                'app': {'langs': [], 'name': None, 'id': self.app_id_2},
                'module': {'name': {}, 'id': 0},
                'app_deleted': False, 'submissions': 1},
            'key': ['exports_forms_analytics_domain', self.app_id_2,
                    'my://crazy.xmlns/app']
        }])
