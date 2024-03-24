import datetime
import uuid

from django.test import TestCase
from corehq.apps.app_manager.tests.util import delete_all_apps

from couchforms.analytics import (
    app_has_been_submitted_to_in_last_30_days,
    domain_has_submission_in_last_30_days,
    get_all_xmlns_app_id_pairs_submitted_to_in_domain,
    get_exports_by_form,
    get_first_form_submission_received,
    get_form_analytics_metadata,
    get_last_form_submission_received,
    get_number_of_forms_in_domain,
)

from corehq.apps.es.apps import app_adapter
from corehq.apps.es.client import manager
from corehq.apps.es.forms import form_adapter
from corehq.apps.es.tests.utils import es_test
from corehq.apps.es.users import user_adapter
from corehq.const import MISSING_APP_ID
from corehq.form_processor.interfaces.processor import FormProcessorInterface
from corehq.form_processor.models import XFormInstance
from corehq.form_processor.tests.utils import (
    FormProcessorTestUtils,
    create_form_for_test,
)
from corehq.form_processor.utils import TestFormMetadata
from corehq.util.test_utils import (
    DocTestMixin,
    disable_quickcache,
    flaky_slow,
    get_form_ready_to_save,
)
from testapps.test_pillowtop.utils import process_pillow_changes


@es_test(requires=[form_adapter, app_adapter], setup_class=True)
@disable_quickcache
class ExportsFormsAnalyticsTest(TestCase, DocTestMixin):
    maxDiff = None

    @classmethod
    def setUpClass(cls):
        super(ExportsFormsAnalyticsTest, cls).setUpClass()
        from casexml.apps.case.tests.util import delete_all_xforms

        from corehq.apps.app_manager.models import Application, Form, Module
        delete_all_xforms()
        delete_all_apps()

        cls.domain = 'exports_forms_analytics_domain'
        cls.app_id_1 = 'a' + uuid.uuid4().hex
        cls.app_id_2 = 'b' + uuid.uuid4().hex
        cls.app_id_3 = 'c' + uuid.uuid4().hex
        cls.xmlns_1 = 'my://crazy.xmlns/'
        cls.xmlns_2 = 'my://crazy.xmlns/app'
        cls.xmlns_3 = 'my://crazy.xmlns/deleted-app'
        cls.apps = [
            Application(_id=cls.app_id_2, domain=cls.domain,
                        modules=[Module(forms=[Form(xmlns=cls.xmlns_2)])]),
            Application(_id=cls.app_id_3, domain=cls.domain,
                        modules=[Module(forms=[Form(xmlns=cls.xmlns_3)])])
        ]
        for app in cls.apps:
            app.save()
        cls.apps[1].delete_app()
        cls.apps[1].save()
        cls.forms = [
            create_form_for_test(domain=cls.domain, app_id=cls.app_id_1, xmlns=cls.xmlns_1, save=False),
            create_form_for_test(domain=cls.domain, app_id=cls.app_id_1, xmlns=cls.xmlns_1, save=False),
            create_form_for_test(domain=cls.domain, app_id=cls.app_id_2, xmlns=cls.xmlns_2, save=False),
            create_form_for_test(domain=cls.domain, app_id=cls.app_id_3, xmlns=cls.xmlns_3, save=False),
        ]
        cls.error_forms = [create_form_for_test(domain=cls.domain, state=XFormInstance.ERROR, save=False)]
        cls.all_forms = cls.forms + cls.error_forms

        for app in cls.apps:
            app_adapter.index(app, refresh=True)
        for form in cls.all_forms:
            form_adapter.index(form, refresh=True)

    @classmethod
    def tearDownClass(cls):
        for app in cls.apps:
            app.delete()
        super(ExportsFormsAnalyticsTest, cls).tearDownClass()

    def test_get_form_analytics_metadata__no_match(self):
        self.assertIsNone(
            get_form_analytics_metadata(self.domain, self.app_id_1, self.xmlns_2))

    def test_get_form_analytics_metadata__no_app(self):
        self.assertEqual(
            get_form_analytics_metadata(self.domain, self.app_id_1, self.xmlns_1),
            {'submissions': 2, 'xmlns': 'my://crazy.xmlns/'}
        )

    @flaky_slow
    def test_get_form_analytics_metadata__app(self):
        self.assertEqual(get_form_analytics_metadata(self.domain, self.app_id_2, self.xmlns_2), {
            'app': {'id': self.app_id_2, 'langs': [], 'name': None},
            'app_deleted': False,
            'form': {'id': 0, 'name': {}},
            'module': {'id': 0, 'name': {}},
            'submissions': 1,
            'xmlns': 'my://crazy.xmlns/app'
        })

    @flaky_slow
    def test_get_exports_by_form(self):
        # Call this twice, since the couchdb `update_after` to force couchdb to return the right results
        get_exports_by_form(self.domain)
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
        }, {
            'value': {
                'xmlns': 'my://crazy.xmlns/deleted-app',
                'form': {'name': {}, 'id': 0},
                'app': {'langs': [], 'name': None, 'id': self.app_id_3},
                'module': {'name': {}, 'id': 0},
                'app_deleted': True, 'submissions': 1,
            },
            'key': ['exports_forms_analytics_domain', self.app_id_3,
                    'my://crazy.xmlns/deleted-app']
        }])

    def test_get_exports_by_form_es(self):
        self.assertEqual(get_exports_by_form(self.domain, use_es=True), [{
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
        }, {
            'value': {
                'xmlns': 'my://crazy.xmlns/deleted-app',
                'submissions': 1,
                'form': {'name': {}, 'id': 0},
                'app': {'langs': [], 'name': None, 'id': self.app_id_3},
                'module': {'name': {}, 'id': 0},
                'app_deleted': True
            },
            'key': ['exports_forms_analytics_domain', self.app_id_3,
                    'my://crazy.xmlns/deleted-app']
        }])

        # We still get the form counts when excluding deleted apps
        self.assertEqual(get_exports_by_form(self.domain, use_es=True, exclude_deleted_apps=True), [{
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
        }, {
            'value': {
                'xmlns': 'my://crazy.xmlns/deleted-app',
                'submissions': 1,
            },
            'key': ['exports_forms_analytics_domain', self.app_id_3,
                    'my://crazy.xmlns/deleted-app']
        }])


@es_test(requires=[form_adapter, user_adapter], setup_class=True)
@disable_quickcache
class CouchformsESAnalyticsTest(TestCase):
    domain = 'hqadmin-es-accessor'

    @classmethod
    def setUpClass(cls):
        super(CouchformsESAnalyticsTest, cls).setUpClass()

        cls.now = datetime.datetime.utcnow()
        cls._60_days = datetime.timedelta(days=60)
        cls.domain = 'my_crazy_analytics_domain'
        cls.app_id = uuid.uuid4().hex
        cls.xmlns = 'my://crazy.xmlns/'

        def create_form(received_on, app_id=cls.app_id, xmlns=cls.xmlns):
            metadata = TestFormMetadata(domain=cls.domain, app_id=app_id,
                                        xmlns=xmlns, received_on=received_on)
            form = get_form_ready_to_save(metadata, is_db_test=True)
            form_processor = FormProcessorInterface(domain=cls.domain)
            form_processor.save_processed_models([form])
            return form

        def create_forms_and_sync_to_es():
            forms = []
            with process_pillow_changes('xform-pillow', {'skip_ucr': True}):
                with process_pillow_changes('DefaultChangeFeedPillow'):
                    for received_on in [cls.now, cls.now - cls._60_days]:
                        forms.append(create_form(received_on))
                    forms.append(create_form(cls.now, app_id=None, xmlns="system"))
            return forms

        from casexml.apps.case.tests.util import delete_all_xforms
        delete_all_xforms()
        cls.forms = create_forms_and_sync_to_es()
        manager.index_refresh(form_adapter.index_name)

    @classmethod
    def tearDownClass(cls):
        FormProcessorTestUtils.delete_all_cases_forms_ledgers(cls.domain)
        super(CouchformsESAnalyticsTest, cls).tearDownClass()

    def test_get_number_of_forms_in_domain(self):
        self.assertEqual(
            get_number_of_forms_in_domain(self.domain),
            len(self.forms)
        )

    def test_domain_has_submission_in_last_30_days(self):
        self.assertEqual(
            domain_has_submission_in_last_30_days(self.domain), True)

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
            {(self.xmlns, self.app_id), ("system", MISSING_APP_ID)})
