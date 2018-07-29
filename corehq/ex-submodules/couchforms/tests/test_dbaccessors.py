from __future__ import absolute_import
from __future__ import unicode_literals
import datetime
from django.test import TestCase

from corehq.form_processor.tests.utils import FormProcessorTestUtils
from corehq.form_processor.utils import get_simple_wrapped_form, TestFormMetadata
from couchforms.dbaccessors import (
    get_forms_by_type,
    get_form_ids_by_type,
    get_deleted_form_ids_for_user,
    get_form_ids_for_user,
)
from couchforms.models import XFormInstance, XFormError


class TestDBAccessors(TestCase):

    @classmethod
    def setUpClass(cls):
        super(TestDBAccessors, cls).setUpClass()
        from casexml.apps.case.tests.util import delete_all_xforms
        delete_all_xforms()
        cls.domain = 'evelyn'
        cls.now = datetime.datetime(2017, 10, 31)
        cls.user_id1 = 'xzy'
        cls.user_id2 = 'abc'

        metadata1 = TestFormMetadata(
            domain=cls.domain,
            user_id=cls.user_id1,
            received_on=cls.now - datetime.timedelta(days=10),
        )
        metadata2 = TestFormMetadata(
            domain=cls.domain,
            user_id=cls.user_id2,
            received_on=cls.now,
        )

        cls.xform1 = get_simple_wrapped_form('123', metadata=metadata1)
        cls.xform2 = get_simple_wrapped_form('456', metadata=metadata2)

        xform_error = get_simple_wrapped_form('789', metadata=metadata2)
        xform_error = XFormError.wrap(xform_error.to_json())
        xform_error.save()

        cls.xform_deleted = get_simple_wrapped_form('101', metadata=metadata2)
        cls.xform_deleted.doc_type += '-Deleted'
        cls.xform_deleted.save()

        cls.xforms = [
            cls.xform1,
            cls.xform2,
        ]
        cls.xform_errors = [xform_error]

    @classmethod
    def tearDownClass(cls):
        FormProcessorTestUtils.delete_all_xforms(cls.domain)
        super(TestDBAccessors, cls).tearDownClass()

    def test_get_form_ids_by_type_xforminstance(self):
        form_ids = get_form_ids_by_type(self.domain, 'XFormInstance')
        self.assertEqual(len(form_ids), len(self.xforms))
        self.assertEqual(set(form_ids), {form._id for form in self.xforms})

    def test_get_form_ids_by_type_xformerror(self):
        form_ids = get_form_ids_by_type(self.domain, 'XFormError')
        self.assertEqual(len(form_ids), len(self.xform_errors))
        self.assertEqual(set(form_ids), {form._id for form in self.xform_errors})

    def test_get_form_ids_by_type_bounded(self):

        def assert_forms_in_range(start, end, forms):
            form_ids = get_form_ids_by_type(self.domain, 'XFormInstance',
                                            start=start, end=end)
            self.assertEqual(set(form_ids), {form._id for form in forms})

        before_both = datetime.date(2017, 9, 1)
        in_between = datetime.date(2017, 10, 25)
        after_both = datetime.date(2017, 11, 1)

        assert_forms_in_range(before_both, after_both, [self.xform1, self.xform2])
        assert_forms_in_range(before_both, in_between, [self.xform1])
        assert_forms_in_range(in_between, after_both, [self.xform2])

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

    def test_get_deleted_form_ids_for_user(self):
        ids = get_deleted_form_ids_for_user(self.user_id2)
        self.assertEqual(len(ids), 1)
        self.assertEqual(ids[0], self.xform_deleted.form_id)

        ids = get_deleted_form_ids_for_user(self.user_id1)
        self.assertEqual(len(ids), 0)

    def test_get_form_ids_for_user(self):
        ids = get_form_ids_for_user(self.domain, self.user_id1)
        self.assertEqual(len(ids), 1)
        self.assertEqual(ids[0], self.xforms[0].form_id)

        ids = get_form_ids_for_user(self.domain, self.user_id2)
        self.assertEqual(len(ids), 1)
        self.assertEqual(ids[0], self.xforms[1].form_id)
