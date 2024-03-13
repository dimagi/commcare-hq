from datetime import datetime
from tempfile import NamedTemporaryFile
from unittest.mock import patch
from uuid import uuid4
from zipfile import ZipFile

from django.test import SimpleTestCase, TestCase

from attrs import define, field
from freezegun import freeze_time

from dimagi.utils.parsing import json_format_datetime

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.es import DomainES, form_adapter
from corehq.apps.es.domains import domain_adapter
from corehq.apps.es.tests.utils import es_test
from corehq.apps.reports.tasks import (
    _get_question_id_for_attachment,
    _make_unique_filename,
    _write_attachments_to_file,
    get_domains_to_update_es_filter,
)
from corehq.form_processor.tests.utils import create_form_for_test


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


@es_test(requires=[domain_adapter, form_adapter], setup_class=True)
class TestGetDomainsToUpdateESFilter(TestCase):
    def test_calculated_properties_never_updated_is_included(self):
        domain = self.index_domain('never-updated')
        self.assertFalse(hasattr(domain, 'cp_last_updated'))

        domains_filter = get_domains_to_update_es_filter()
        results = DomainES().filter(domains_filter).fields(['_id', 'name']).run().hits

        self.assertEqual(results, [{'_id': domain._id, 'name': domain.name}])

    @freeze_time('2020-01-10')
    def test_calculated_properties_updated_over_one_week_ago_is_included(self):
        domain = self.index_domain('cp-over-one-week', cp_last_updated=datetime(2020, 1, 2, 23, 59))

        domains_filter = get_domains_to_update_es_filter()
        results = DomainES().filter(domains_filter).fields(['_id', 'name']).run().hits

        self.assertEqual(results, [{'_id': domain._id, 'name': domain.name}])

    @freeze_time('2020-01-10')
    def test_calculated_properties_updated_exactly_one_week_ago_is_excluded(self):
        self.index_domain('cp-one-week', cp_last_updated=datetime(2020, 1, 3))

        domains_filter = get_domains_to_update_es_filter()
        results = DomainES().filter(domains_filter).fields(['_id', 'name']).run().hits

        self.assertEqual(results, [])

    @freeze_time('2020-01-10')
    def test_calculated_properties_updated_less_than_one_week_ago_is_excluded(self):
        self.index_domain('cp-less-than-one-week', cp_last_updated=datetime(2020, 1, 4))

        domains_filter = get_domains_to_update_es_filter()
        results = DomainES().filter(domains_filter).fields(['_id', 'name']).run().hits

        self.assertEqual(results, [])

    @freeze_time('2020-01-10')
    def test_form_submission_in_the_last_day_is_included(self):
        domain = self.index_domain('form-from-today', cp_last_updated=datetime(2020, 1, 9))
        self.index_form(domain.name, received_on=datetime(2020, 1, 9, 0, 0))

        domains_filter = get_domains_to_update_es_filter()
        results = DomainES().filter(domains_filter).fields(['_id', 'name']).run().hits

        self.assertEqual(results, [{'_id': domain._id, 'name': domain.name}])

    @freeze_time('2020-01-10')
    def test_form_submission_over_one_day_ago_is_excluded(self):
        domain = self.index_domain('form-from-yesterday', cp_last_updated=datetime(2020, 1, 9))
        self.index_form(domain.name, received_on=datetime(2020, 1, 8, 23, 59))

        domains_filter = get_domains_to_update_es_filter()
        results = DomainES().filter(domains_filter).fields(['_id', 'name']).run().hits

        self.assertEqual(results, [])

    @freeze_time('2020-01-10')
    def test_inactive_domain_is_excluded(self):
        self.index_domain('inactive-domain', active=False)

        domains_filter = get_domains_to_update_es_filter()
        results = DomainES().filter(domains_filter).fields(['_id', 'name']).run().hits

        self.assertEqual(results, [])

    def index_domain(self, name, active=True, cp_last_updated=None):
        domain = create_domain(name, active)
        self.addCleanup(domain.delete)
        if cp_last_updated:
            domain.cp_last_updated = json_format_datetime(cp_last_updated)
        domain_adapter.index(domain, refresh=True)
        self.addCleanup(domain_adapter.delete, domain._id, refresh=True)
        return domain

    def index_form(self, domain, received_on):
        xform = create_form_for_test(domain, received_on=received_on)
        form_adapter.index(xform, refresh=True)
        self.addCleanup(form_adapter.delete, xform.form_id, refresh=True)
        return xform


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
