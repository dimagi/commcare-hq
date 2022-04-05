import os
from unittest.mock import patch

from django.core.cache import cache
from django.test import SimpleTestCase

from testil import eq

from corehq.apps.app_manager.xform import XForm
from corehq.apps.reports.exceptions import EditFormValidationError
from corehq.apps.reports.tasks import summarize_user_counts
from corehq.apps.reports.util import get_user_id_from_form, validate_xform_for_edit
from corehq.form_processor.exceptions import XFormNotFound
from corehq.form_processor.models import XFormInstance
from corehq.form_processor.utils import TestFormMetadata
from corehq.util.test_utils import TestFileMixin, get_form_ready_to_save

DOMAIN = 'test_domain'
USER_ID = "5bc1315c-da6f-466d-a7c4-4580bc84a7b9"


class TestValidateXFormForEdit(SimpleTestCase, TestFileMixin):
    file_path = ('edit_forms',)
    root = os.path.dirname(__file__)

    def test_bad_calculate(self):
        source = self.get_xml('bad_calculate')
        xform = XForm(source)
        with self.assertRaises(EditFormValidationError):
            validate_xform_for_edit(xform)


class TestSummarizeUserCounts(SimpleTestCase):
    def test_summarize_user_counts(self):
        self.assertEqual(
            summarize_user_counts({'a': 1, 'b': 10, 'c': 2}, n=0),
            {(): 13},
        )
        self.assertEqual(
            summarize_user_counts({'a': 1, 'b': 10, 'c': 2}, n=1),
            {'b': 10, (): 3},
        )
        self.assertEqual(
            summarize_user_counts({'a': 1, 'b': 10, 'c': 2}, n=2),
            {'b': 10, 'c': 2, (): 1},
        )
        self.assertEqual(
            summarize_user_counts({'a': 1, 'b': 10, 'c': 2}, n=3),
            {'a': 1, 'b': 10, 'c': 2, (): 0},
        )
        self.assertEqual(
            summarize_user_counts({'a': 1, 'b': 10, 'c': 2}, n=4),
            {'a': 1, 'b': 10, 'c': 2, (): 0},
        )


def test_get_user_id():
    form_id = "acca290f-22fc-4c5c-8cce-ee253ca5678b"
    reset_cache(form_id)
    with patch.object(XFormInstance.objects, "get_form", get_form):
        eq(get_user_id_from_form(form_id), USER_ID)


def test_get_user_id_cached():
    form_id = "d1667406-319f-4d0c-9091-0d6c0032363a"
    reset_cache(form_id, USER_ID)
    with patch.object(XFormInstance.objects, "get_form", form_not_found):
        eq(get_user_id_from_form(form_id), USER_ID)


def test_get_user_id_not_found():
    form_id = "73bfc6a5-c66e-4b17-be6d-45513511e1ef"
    reset_cache(form_id)
    with patch.object(XFormInstance.objects, "get_form", form_not_found):
        eq(get_user_id_from_form(form_id), None)

    with patch.object(XFormInstance.objects, "get_form", get_form):
        # null value should not be cached
        eq(get_user_id_from_form(form_id), USER_ID)


def get_form(form_id):
    metadata = TestFormMetadata(domain="test", user_id=USER_ID)
    return get_form_ready_to_save(metadata, form_id=form_id)


def form_not_found(form_id):
    raise XFormNotFound(form_id)


def reset_cache(form_id, value=None):
    key = f'xform-{form_id}-user_id'
    if value is None:
        cache.delete(key)
    else:
        cache.set(key, value, 5)
