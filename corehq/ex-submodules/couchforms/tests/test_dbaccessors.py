import datetime
from django.test import TestCase

from corehq.apps.hqadmin.dbaccessors import get_number_of_forms_in_all_domains
from corehq.form_processor.tests.utils import FormProcessorTestUtils
from couchforms.dbaccessors import get_forms_by_type, \
    get_form_ids_by_type
from couchforms.models import XFormInstance, XFormError


class TestDBAccessors(TestCase):
    dependent_apps = ['corehq.couchapps', 'corehq.apps.domain', 'corehq.form_processor']

    @classmethod
    def setUpClass(cls):
        from casexml.apps.case.tests.util import delete_all_xforms
        delete_all_xforms()
        cls.domain = 'evelyn'
        cls.now = datetime.datetime.utcnow()
        cls.xforms = [
            XFormInstance(_id='xform_1',
                          received_on=cls.now - datetime.timedelta(days=10)),
            XFormInstance(_id='xform_2', received_on=cls.now)
        ]
        cls.xform_errors = [XFormError(_id='xform_error_1')]

        for form in cls.xforms + cls.xform_errors:
            form.domain = cls.domain
            form.save()

    @classmethod
    def tearDownClass(cls):
        FormProcessorTestUtils.delete_all_xforms(cls.domain)

    def test_get_forms_by_type_xforminstance(self):
        forms = get_forms_by_type(self.domain, 'XFormInstance', limit=10)
        self.assertEqual(len(forms), len(self.xforms))
        self.assertEqual({form._id for form in forms},
                         {form._id for form in self.xforms})
        for form in forms:
            self.assertIsInstance(form, XFormInstance)

    def test_get_forms_by_type_xformerror(self):
        forms = get_forms_by_type(self.domain, 'XFormError', limit=10)
        self.assertEqual(len(forms), len(self.xform_errors))
        self.assertEqual({form._id for form in forms},
                         {form._id for form in self.xform_errors})
        for form in forms:
            self.assertIsInstance(form, XFormError)

    def test_get_form_ids_by_type(self):
        form_ids = get_form_ids_by_type(self.domain, 'XFormError')
        self.assertEqual(form_ids, [form._id for form in self.xform_errors])

    def test_get_number_of_forms_in_all_domains(self):
        self.assertEqual(
            get_number_of_forms_in_all_domains(),
            len(self.xforms)
        )
