import uuid
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.core.files.uploadedfile import UploadedFile
from django.test import TestCase
from unmagic import fixture

from corehq.apps.receiverwrapper.util import submit_form_locally
from corehq.form_processor.models import XFormInstance
from corehq.form_processor.submission_validation import (
    _collect_image_references,
    check_image_attachments,
)
from corehq.form_processor.tests.utils import FormProcessorTestUtils, sharded
from corehq.form_processor.utils.xform import (
    FormSubmissionBuilder,
    TestFormMetadata,
)


def _stub_xform(
    attachments,
    form_data,
    *,
    domain='d',
    app_id='a',
    form_id='f',
):
    return SimpleNamespace(
        attachments=attachments,
        form_data=form_data,
        domain=domain,
        app_id=app_id,
        form_id=form_id,
    )


@fixture
def capture_sentry():
    with patch(
        'corehq.form_processor.submission_validation.sentry_sdk'
    ) as sdk:
        # `new_scope` is used as a context manager; the test only inspects
        # `capture_message` calls so we keep the rest minimal.
        sdk.new_scope.return_value.__enter__.return_value = SimpleNamespace(
            set_tag=lambda *a, **kw: None,
            set_extra=lambda *a, **kw: None,
            fingerprint=None,
        )
        yield sdk.capture_message


@capture_sentry
def test_no_alert_when_image_answers_match_attachments():
    xform = _stub_xform(
        attachments={'pic1.jpg': object(), 'pic2.png': object()},
        form_data={'photo_a': 'pic1.jpg', 'photo_b': 'pic2.png'},
    )
    check_image_attachments(sender=None, xform=xform)
    assert capture_sentry().call_count == 0


@capture_sentry
def test_alert_when_referenced_image_is_missing():
    xform = _stub_xform(
        attachments={'pic1.jpg': object()},
        form_data={'photo_a': 'pic1.jpg', 'photo_b': 'deleted.jpg'},
    )
    check_image_attachments(sender=None, xform=xform)
    assert capture_sentry().call_count == 1


@capture_sentry
def test_alert_when_attachment_has_no_matching_answer():
    xform = _stub_xform(
        attachments={'pic1.jpg': object(), 'orphan.jpg': object()},
        form_data={'photo_a': 'pic1.jpg'},
    )
    check_image_attachments(sender=None, xform=xform)
    assert capture_sentry().call_count == 1


@capture_sentry
def test_no_alert_when_form_has_no_images():
    xform = _stub_xform(
        attachments={},
        form_data={'name': 'Alice', 'age': '42'},
    )
    check_image_attachments(sender=None, xform=xform)
    assert capture_sentry().call_count == 0


@capture_sentry
def test_non_image_attachments_are_ignored():
    xform = _stub_xform(
        attachments={'audio.mp3': object(), 'pic.jpg': object()},
        form_data={'photo': 'pic.jpg', 'recording': 'audio.mp3'},
    )
    check_image_attachments(sender=None, xform=xform)
    assert capture_sentry().call_count == 0


@pytest.mark.parametrize(
    'ext', ['.jpg', '.JPG', '.jpeg', '.png', '.gif', '.heic', '.bmp', '.webp']
)
def test_image_extensions_are_recognised_case_insensitively(ext):
    refs = _collect_image_references({'q': f'photo{ext}'})
    assert refs == {f'photo{ext}'}


def test_nested_form_data_is_walked():
    form_data = {
        'group': {
            'subgroup': {'photo': 'nested.jpg'},
            'gallery': [{'photo': 'one.jpg'}, {'photo': 'two.jpg'}],
        },
        'top': 'top.png',
    }
    assert _collect_image_references(form_data) == {
        'nested.jpg',
        'one.jpg',
        'two.jpg',
        'top.png',
    }


@sharded
class TestCheckImageAttachmentsCachingFootprint(TestCase):
    """
    Documents what is cached on the ``xform`` instance at the moment the
    ``successful_form_received`` signal fires, by counting how often
    ``convert_xform_to_json`` and ``XFormInstance.get_attachment`` run
    during submission, and how many additional calls
    ``check_image_attachments`` itself causes.

    With ``instance_json`` cached on ``xform._form_json`` during
    ``_create_new_xform``, the form XML is parsed exactly once per
    submission and the handler does no I/O of its own.
    """

    domain = 'submission-validation-tests'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        FormProcessorTestUtils.delete_all_xforms(cls.domain)

    @classmethod
    def tearDownClass(cls):
        FormProcessorTestUtils.delete_all_xforms(cls.domain)
        super().tearDownClass()

    def _build_form_xml(self, form_id):
        # Reference an image filename as the answer to a question so that
        # the handler exercises its `form_data` traversal path.
        return FormSubmissionBuilder(
            form_id=form_id,
            metadata=TestFormMetadata(domain=self.domain),
            form_properties={'photo': 'pic.jpg'},
        ).as_xml_string()

    def test_caching_footprint_at_signal_time(self):
        form_id = uuid.uuid4().hex
        form_xml = self._build_form_xml(form_id)
        attachments = {
            'pic.jpg': UploadedFile(
                BytesIO(b'fake'),
                'pic.jpg',
                content_type='image/jpeg',
                size=4,
            )
        }

        convert_calls = []
        get_attachment_calls = []
        pre_handler_state = {}

        # `convert_xform_to_json` is re-exported from
        # `corehq.form_processor.utils` and imported with a module-local
        # name in `parsers.form`; patch both bindings so every call site
        # used during submission funnels through the spy.
        from corehq.form_processor import utils as form_utils
        from corehq.form_processor.parsers import form as form_parser

        original_convert = form_utils.convert_xform_to_json
        original_get_attachment = XFormInstance.get_attachment

        def spy_convert(*args, **kwargs):
            convert_calls.append(args)
            return original_convert(*args, **kwargs)

        def spy_get_attachment(self, name):
            get_attachment_calls.append(name)
            return original_get_attachment(self, name)

        # Wrap the registered receiver so we can snapshot the spy state
        # *before* the handler does its own work.
        def wrapped_handler(sender, xform, **kwargs):
            pre_handler_state['convert'] = list(convert_calls)
            pre_handler_state['form_xml_fetches'] = [
                name for name in get_attachment_calls if name == 'form.xml'
            ]
            return check_image_attachments(
                sender=sender, xform=xform, **kwargs
            )

        from couchforms.signals import successful_form_received

        successful_form_received.disconnect(
            dispatch_uid='check_image_attachments'
        )
        successful_form_received.connect(
            wrapped_handler,
            dispatch_uid='check_image_attachments_test',
        )
        try:
            with (
                patch.object(
                    form_utils,
                    'convert_xform_to_json',
                    spy_convert,
                ),
                patch.object(
                    form_parser,
                    'convert_xform_to_json',
                    spy_convert,
                ),
                patch.object(
                    XFormInstance,
                    'get_attachment',
                    spy_get_attachment,
                ),
            ):
                submit_form_locally(
                    form_xml,
                    self.domain,
                    attachments=attachments,
                )
        finally:
            successful_form_received.disconnect(
                dispatch_uid='check_image_attachments_test'
            )
            successful_form_received.connect(
                check_image_attachments,
                dispatch_uid='check_image_attachments',
            )

        # Pre-handler state: What processing has already done:
        # `_create_new_xform` parses the submitted XML once and caches
        # the result on `xform._form_json`. Every subsequent access to
        # `form_data` during processing (e.g. `instance.metadata` in
        # `_invalidate_caches`) reuses that cached JSON instead of
        # reparsing.
        assert len(pre_handler_state['convert']) == 1, (
            'submission processing should parse the form exactly once '
            'before the signal fires'
        )
        # The handler reads `xform.form_data`, which returns the cached
        # `_form_json`, so the handler adds no extra parse.
        handler_convert_calls = len(convert_calls) - len(
            pre_handler_state['convert']
        )
        assert handler_convert_calls == 0, (
            'handler must not trigger an additional XML-to-JSON parse'
        )

        # `_form_json` is populated up-front from the raw XML the
        # submission was parsed from, so `form_data` never has to call
        # `get_xml()`. The handler therefore does not trigger any
        # `form.xml` blob fetch on its own.
        form_xml_fetches_total = [
            name for name in get_attachment_calls if name == 'form.xml'
        ]
        handler_form_xml_fetches = len(form_xml_fetches_total) - len(
            pre_handler_state['form_xml_fetches']
        )
        assert handler_form_xml_fetches == 0, (
            'handler must not trigger an additional form.xml blob fetch'
        )
