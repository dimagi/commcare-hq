from tempfile import NamedTemporaryFile
from unittest.mock import patch
from uuid import uuid4
from zipfile import ZipFile

from attrs import define, field

from django.test import SimpleTestCase

from corehq.apps.reports.tasks import (
    _get_question_id_for_attachment,
    _make_unique_filename,
    _write_attachments_to_file,
)


class GetQuestionIdTests(SimpleTestCase):

    def test_returns_question_id_when_found(self):
        form = {'attachment': 'my_attachment'}

        result = _get_question_id_for_attachment(form, 'my_attachment')
        self.assertEqual(result, 'attachment')

    def test_returns_question_id_when_found_in_nested_form(self):
        nested_form = {'attachment': 'my_attachment'}
        form = {'nested': nested_form}

        result = _get_question_id_for_attachment(form, 'my_attachment')
        self.assertEqual(result, 'nested-attachment')

    def test_returns_question_id_when_found_in_list(self):
        nested_form = {'attachment': 'my_attachment'}
        form = {'nested_list': [nested_form]}

        result = _get_question_id_for_attachment(form, 'my_attachment')
        self.assertEqual(result, 'nested_list-attachment')

    def test_handles_invalid_list_item(self):
        form = {'bad_list': ['']}

        result = _get_question_id_for_attachment(form, 'my_attachment')
        self.assertIsNone(result)

    def test_returns_none_when_not_found(self):
        form = {}

        result = _get_question_id_for_attachment(form, 'my_attachment')
        self.assertIsNone(result)

    def test_returns_question_id_when_found_as_abs_path_basename(self):
        form = {'attachment': '/path/to/my/attachment.ext'}

        result = _get_question_id_for_attachment(form, 'attachment.ext')
        self.assertEqual(result, 'attachment')

    def test_returns_none_when_found_as_rel_path_basename(self):
        """
        The original bug this aims to solve only occurs for absolute paths
        To minimize impact of the change, only look at basenames of absolute paths
        """
        form = {'attachment': 'path/to/my/attachment.ext'}

        result = _get_question_id_for_attachment(form, 'attachment.ext')
        self.assertIsNone(result)


@patch("soil.DownloadBase.set_progress")
class TestMultimediaZipFile(SimpleTestCase):

    def test_files_with_same_name_should_be_uniqued(self, ignore):
        forms = [{
            "form": FakeForm("deadcafe"),
            "case_ids": [],
            "username": "someone",
            "attachments": [
                _attachment("img"),
                _attachment("img"),
                _attachment("img"),
            ]
        }]
        with NamedTemporaryFile() as fh:

            _write_attachments_to_file(fh.name, 1, forms, {})

            zip = ZipFile(fh.name)
            names = zip.namelist()
            self.assertEqual(names, [
                "img-someone-form_deadcafe.jpg",
                "img-someone-form_deadcafe-2.jpg",
                "img-someone-form_deadcafe-3.jpg",
            ])


class TestMakeUniqueFilename(SimpleTestCase):

    def test_collision_with_generated_unique_name(self):
        unique_names = {}
        self.assertEqual(_make_unique_filename("pic.jpg", unique_names), "pic.jpg")
        self.assertEqual(_make_unique_filename("pic.jpg", unique_names), "pic-2.jpg")
        self.assertEqual(_make_unique_filename("pic-2.jpg", unique_names), "pic-2-2.jpg")

    def test_collision_with_multiple_generated_names(self):
        unique_names = {}
        self.assertEqual(_make_unique_filename("pic-2.jpg", unique_names), "pic-2.jpg")
        self.assertEqual(_make_unique_filename("pic-2.jpg", unique_names), "pic-2-2.jpg")
        self.assertEqual(_make_unique_filename("pic.jpg", unique_names), "pic.jpg")
        self.assertEqual(_make_unique_filename("pic.jpg", unique_names), "pic-2-3.jpg")  # multi-collision


@define
class FakeForm:
    form_id = field()

    def get_attachment(self, name):
        return b"012345678901234567890123"


def _attachment(question_id):
    return {
        "id": uuid4().hex,
        "name": uuid4().hex,
        "size": 24,
        "question_id": question_id,
        "extension": ".jpg",
        "timestamp": (2023, 8, 9, 21, 36, 20),
    }
