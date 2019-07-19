from __future__ import absolute_import
from __future__ import unicode_literals
import uuid
from django.test import TestCase
from corehq.apps.app_manager.tests.app_factory import AppFactory
from corehq.apps.reports.analytics.couchaccessors import (
    update_reports_analytics_indexes,
    get_all_form_definitions_grouped_by_app_and_xmlns,
    SimpleFormInfo,
    get_all_form_details,
    get_form_details_for_xmlns,
    get_form_details_for_app_and_module,
    get_form_details_for_app_and_xmlns,
    get_form_details_for_app,
)
from six.moves import range


class SetupSimpleAppMixin(object):

    @classmethod
    def class_setup(cls):
        cls.domain = uuid.uuid4().hex
        cls.f1_xmlns = 'xmlns1'
        cls.f2_xmlns = 'xmlns2'
        app_factory = AppFactory(domain=cls.domain)
        module1, form1 = app_factory.new_basic_module('m1', '_casetype')
        module2, form2 = app_factory.new_basic_module('m2', '_casetype2')
        form1.xmlns = cls.f1_xmlns
        form2.xmlns = cls.f2_xmlns
        app_factory.app.save()
        cls.app = app_factory.app
        deleted_app_factory = AppFactory(domain=cls.domain)
        deleted_module1, deleted_form1 = deleted_app_factory.new_basic_module('del-m1', '_casetype3')
        cls.deleted_xmlns = 'xmlns3'
        deleted_form1.xmlns = cls.deleted_xmlns
        deleted_app_factory.app.doc_type = 'Application-Deleted'
        # make sure the ID comes after the primary app
        deleted_app_factory.app._id = '{}z'.format(cls.app.id)
        deleted_app_factory.app.save()
        cls.deleted_app = deleted_app_factory.app
        cls.xmlnses = [cls.f1_xmlns, cls.f2_xmlns, cls.deleted_xmlns]
        update_reports_analytics_indexes()

    def _assert_form_details_match(self, index, details):
        expected_app = self.app if index < 2 else self.deleted_app
        self.assertEqual(expected_app._id, details.app.id)
        self.assertEqual(index % 2, details.module.id)
        self.assertEqual(0, details.form.id)
        self.assertEqual(self.xmlnses[index], details.xmlns)
        self.assertFalse(details.is_user_registration)


class ReportAppAnalyticsTest(SetupSimpleAppMixin, TestCase):

    @classmethod
    def setUpClass(cls):
        super(ReportAppAnalyticsTest, cls).setUpClass()
        cls.class_setup()

    @classmethod
    def tearDownClass(cls):
        super(ReportAppAnalyticsTest, cls).tearDownClass()
        cls.app.delete()
        cls.deleted_app.delete()

    def test_get_all_form_definitions_grouped_by_app_and_xmlns_no_data(self):
        self.assertEqual([], get_all_form_definitions_grouped_by_app_and_xmlns('missing'))

    def test_get_all_form_definitions_grouped_by_app_and_xmlns(self):
        self.assertEqual(
            [SimpleFormInfo(self.app._id, self.f1_xmlns),
             SimpleFormInfo(self.app._id, self.f2_xmlns),
             SimpleFormInfo(self.deleted_app._id, self.deleted_xmlns)],
            get_all_form_definitions_grouped_by_app_and_xmlns(self.domain)
        )

    def test_get_all_form_details_no_data(self):
        self.assertEqual([], get_all_form_details('missing'))

    def test_get_all_form_details(self):
        app_structures = get_all_form_details(self.domain)
        self.assertEqual(3, len(app_structures))
        for i, details in enumerate(app_structures):
            self._assert_form_details_match(i, details)

    def test_get_all_form_details_active(self):
        details = get_all_form_details(self.domain, deleted=False)
        self.assertEqual(2, len(details))
        for i, detail in enumerate(details):
            self._assert_form_details_match(i, detail)

    def test_get_all_form_details_deleted(self):
        details = get_all_form_details(self.domain, deleted=True)
        self.assertEqual(1, len(details))
        self._assert_form_details_match(2, details[0])

    def test_get_form_details_for_xmlns_no_data(self):
        self.assertEqual([], get_form_details_for_xmlns('missing', 'missing'))
        self.assertEqual([], get_form_details_for_xmlns(self.domain, 'missing'))
        self.assertEqual([], get_form_details_for_xmlns('missing', self.f1_xmlns))

    def test_get_form_details_for_xmlns(self):
        [details_1] = get_form_details_for_xmlns(self.domain, self.f1_xmlns)
        [details_2] = get_form_details_for_xmlns(self.domain, self.f2_xmlns)
        for i, details in enumerate([details_1, details_2]):
            self._assert_form_details_match(i, details)

    def test_get_form_details_for_app_no_data(self):
        self.assertEqual([], get_form_details_for_app('missing', 'missing'))
        self.assertEqual([], get_form_details_for_app('missing', self.app.id))
        self.assertEqual([], get_form_details_for_app(self.domain, 'missing'))

    def test_get_form_details_for_app(self):
        details = get_form_details_for_app(self.domain, self.app.id)
        for i, detail in enumerate(details):
            self._assert_form_details_match(i, detail)

    def test_get_form_details_for_app_and_module_no_data(self):
        self.assertEqual([], get_form_details_for_app_and_module('missing', self.app.id, 0))
        self.assertEqual([], get_form_details_for_app_and_module(self.domain, 'missing', 0))
        self.assertEqual([], get_form_details_for_app_and_module(self.domain, self.app.id, 3))

    def test_get_form_details_for_app_and_module(self):
        for i in range(2):
            [details] = get_form_details_for_app_and_module(self.domain, self.app.id, i)
            self._assert_form_details_match(i, details)

    def test_get_form_details_for_app_and_xmlns_no_data(self):
        self.assertEqual([], get_form_details_for_app_and_xmlns('missing', self.app.id, self.f1_xmlns))
        self.assertEqual([], get_form_details_for_app_and_xmlns(self.domain, 'missing', self.f1_xmlns))
        self.assertEqual([], get_form_details_for_app_and_xmlns(self.domain, self.app.id, 'missing'))
        self.assertEqual(
            [], get_form_details_for_app_and_xmlns(self.domain, self.app.id, self.f1_xmlns, deleted=True)
        )

    def test_get_form_details_for_app_and_xmlns(self):
        for i in range(2):
            [details] = get_form_details_for_app_and_xmlns(self.domain, self.app.id, self.xmlnses[i])
            self._assert_form_details_match(i, details)
