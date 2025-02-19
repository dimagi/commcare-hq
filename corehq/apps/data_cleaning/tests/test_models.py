from django.test import TestCase

from casexml.apps.case.mock import CaseFactory
from corehq.apps.data_cleaning.models import (
    BulkEditChange,
    EditActionType,
)
from corehq.form_processor.tests.utils import FormProcessorTestUtils


class BulkEditChangeTest(TestCase):
    domain = 'planet'
    case_type = 'island'

    def setUp(self):
        factory = CaseFactory(domain=self.domain)
        self.case = factory.create_case(
            case_type=self.case_type,
            owner_id='q123',
            case_name='Vieques',
            update={
                'nearest_ocean': 'atlantic',
                'town': 'Isabel Segunda',
                'favorite_beach': 'Playa Bastimento',
                'art': '  :)     ',
                'second_favorite_beach': 'no idea',
            },
        )

        super().setUp()

    def tearDown(self):
        FormProcessorTestUtils.delete_all_cases()
        super().tearDown()

    def test_replace(self):
        change = BulkEditChange(
            property='town',
            action_type=EditActionType.REPLACE,
            replace_string='Esperanza',
        )
        self.assertEqual(change.edited_value(self.case), 'Esperanza')

    def test_find_replace(self):
        change = BulkEditChange(
            property='favorite_beach',
            action_type=EditActionType.FIND_REPLACE,
            find_string='Playa',
            replace_string='Punta',
        )
        self.assertEqual(change.edited_value(self.case), 'Punta Bastimento')

    def test_strip(self):
        change = BulkEditChange(
            property='art',
            action_type=EditActionType.STRIP,
        )
        self.assertEqual(change.edited_value(self.case), ':)')

    def test_copy_replace(self):
        change = BulkEditChange(
            property='nearest_ocean',
            action_type=EditActionType.COPY_REPLACE,
            copy_from_property='favorite_beach',
            find_string='Bastimento',
            replace_string='Yallis',
        )
        self.assertEqual(change.edited_value(self.case), 'Playa Yallis')

    def test_title_case(self):
        change = BulkEditChange(
            property='nearest_ocean',
            action_type=EditActionType.TITLE_CASE,
        )
        self.assertEqual(change.edited_value(self.case), 'Atlantic')

    def test_upper_case(self):
        change = BulkEditChange(
            property='town',
            action_type=EditActionType.UPPER_CASE,
        )
        self.assertEqual(change.edited_value(self.case), 'ISABEL SEGUNDA')

    def test_lower_case(self):
        change = BulkEditChange(
            property='town',
            action_type=EditActionType.LOWER_CASE,
        )
        self.assertEqual(change.edited_value(self.case), 'isabel segunda')

    def test_make_empty(self):
        change = BulkEditChange(
            property='nearest_ocean',
            action_type=EditActionType.MAKE_EMPTY,
        )
        self.assertEqual(change.edited_value(self.case), '')

    def test_make_null(self):
        change = BulkEditChange(
            property='nearest_ocean',
            action_type=EditActionType.MAKE_NULL,
        )
        self.assertEqual(change.edited_value(self.case), None)
