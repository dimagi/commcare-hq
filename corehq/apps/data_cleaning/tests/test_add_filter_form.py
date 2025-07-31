from unittest import mock

from django.test import TestCase

from corehq.apps.data_cleaning.forms.filters import AddFilterForm
from corehq.apps.data_cleaning.models.session import BulkEditSession
from corehq.apps.data_cleaning.models.types import (
    DataType,
    FilterMatchType,
)
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.models import WebUser
from corehq.util.test_utils import disable_quickcache


@disable_quickcache
class TestAddFilterForm(TestCase):
    domain = 'dc-add-filter-form-test'
    username = 'someone@cleandata.org'
    case_type = 'plant'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain_obj = create_domain(cls.domain)
        cls.addClassCleanup(cls.domain_obj.delete)

        cls.web_user = WebUser.create(cls.domain, 'tester@datacleaning.org', 'testpwd', None, None)
        cls.addClassCleanup(cls.web_user.delete, cls.domain, deleted_by=None)

        cls._case_props_patcher = mock.patch(
            'corehq.apps.data_cleaning.utils.cases.all_case_properties_by_domain',
            return_value={
                cls.case_type: [
                    'soil_mix',
                    'height',
                    'watered_on',
                    'pot_type',
                ]
            },
        )
        cls._case_props_patcher.start()
        cls.addClassCleanup(cls._case_props_patcher.stop)

    def setUp(self):
        super().setUp()
        self.session = BulkEditSession.objects.new_case_session(
            self.web_user.get_django_user(),
            self.domain,
            self.case_type,
        )

    @staticmethod
    def _get_post_data(
        prop_id,
        data_type,
        text_match_type=None,
        text_value=None,
        number_match_type=None,
        number_value=None,
        date_match_type=None,
        date_value=None,
        datetime_value=None,
        multi_select_match_type=None,
        multi_select_value=None,
    ):
        return {
            'prop_id': prop_id,
            'data_type': data_type,
            'text_match_type': text_match_type,
            'text_value': text_value,
            'number_match_type': number_match_type,
            'number_value': number_value,
            'date_match_type': date_match_type,
            'date_value': date_value,
            'datetime_value': datetime_value,
            'multi_select_match_type': multi_select_match_type,
            'multi_select_value': multi_select_value,
        }

    def test_validation_fails_prop_id_is_required(self):
        data = self._get_post_data('', DataType.TEXT)
        form = AddFilterForm(self.session, data)
        assert not form.is_valid()
        self.assertFormError(
            form,
            field='prop_id',
            errors=[
                'Please select a case property to filter on.',
            ],
        )

    def test_data_type_always_text_if_missing(self):
        data = self._get_post_data(
            'soil_mix',
            '',
            text_match_type=FilterMatchType.EXACT,
            text_value='chunky',
        )
        form = AddFilterForm(self.session, data)
        assert form.is_valid()
        assert 'data_type' in form.cleaned_data
        assert form.cleaned_data['data_type'] == DataType.TEXT

    def test_validation_fails_incorrect_data_type(self):
        data = self._get_post_data('soil_mix', 'not_a_type')
        form = AddFilterForm(self.session, data)
        assert not form.is_valid()
        self.assertFormError(
            form,
            field='data_type',
            errors=[
                'Select a valid choice. not_a_type is not one of the available choices.',
                'Please specify a data type.',
            ],
        )

    def test_missing_match_types(self):
        cases = [
            ('soil_mix', DataType.TEXT, 'text_match_type'),
            ('height', DataType.INTEGER, 'number_match_type'),
            ('watered_on', DataType.DATE, 'date_match_type'),
            ('pot_type', DataType.MULTIPLE_OPTION, 'multi_select_match_type'),
        ]
        for prop_id, data_type, match_field in cases:
            with self.subTest(prop_id=prop_id, data_type=data_type):
                data = self._get_post_data(prop_id, data_type)
                form = AddFilterForm(self.session, data)
                assert not form.is_valid()
                self.assertFormError(form, field=match_field, errors=['Please select a match type.'])

    def test_missing_values_for_text_choices(self):
        required_text_match_types = [mt for mt, _ in FilterMatchType.TEXT_CHOICES]
        for match_type in required_text_match_types:
            with self.subTest(match_type=match_type):
                data = self._get_post_data(
                    'soil_mix',
                    DataType.TEXT,
                    text_match_type=match_type,
                    text_value=None,
                )
                form = AddFilterForm(self.session, data)
                assert not form.is_valid()
                self.assertFormError(
                    form,
                    field='text_value',
                    errors=["Please provide a value or use the 'empty' or 'missing' match types."],
                )

    def test_missing_values_for_number_choices(self):
        required_number_match_types = [mt for mt, _ in FilterMatchType.NUMBER_CHOICES]
        for match_type in required_number_match_types:
            with self.subTest(match_type=match_type):
                data = self._get_post_data(
                    'height',
                    DataType.INTEGER,
                    number_match_type=match_type,
                    number_value=None,
                )
                form = AddFilterForm(self.session, data)
                assert not form.is_valid()
                self.assertFormError(
                    form,
                    field='number_value',
                    errors=["Please provide a value or use the 'empty' or 'missing' match types."],
                )

    def test_missing_values_for_date_choices(self):
        required_date_match_types = [mt for mt, _ in FilterMatchType.DATE_CHOICES]
        for match_type in required_date_match_types:
            with self.subTest(match_type=match_type):
                data = self._get_post_data(
                    'watered_on',
                    DataType.DATE,
                    date_match_type=match_type,
                    date_value=None,
                )
                form = AddFilterForm(self.session, data)
                assert not form.is_valid()
                self.assertFormError(
                    form,
                    field='date_value',
                    errors=[
                        "Please provide a value or use the 'empty' or 'missing' match types.",
                        "Date format should be 'YYYY-MM-DD'",
                    ],
                )

    def test_missing_values_for_multi_select_choices(self):
        required_multi_select_match_types = [mt for mt, _ in FilterMatchType.MULTI_SELECT_CHOICES]
        for match_type in required_multi_select_match_types:
            with self.subTest(match_type=match_type):
                data = self._get_post_data(
                    'pot_type',
                    DataType.MULTIPLE_OPTION,
                    multi_select_match_type=match_type,
                    multi_select_value=None,
                )
                form = AddFilterForm(self.session, data)
                assert not form.is_valid()
                self.assertFormError(
                    form,
                    field='multi_select_value',
                    errors=["Please provide a value or use the 'empty' or 'missing' match types."],
                )

    def test_validation_ok_for_non_value_matches_with_text(self):
        non_value_match_types = [mt for mt, _ in FilterMatchType.ALL_DATA_TYPES_CHOICES]
        for match_type in non_value_match_types:
            with self.subTest(match_type=match_type):
                data = self._get_post_data(
                    'soil_mix',
                    DataType.TEXT,
                    text_match_type=match_type,
                    text_value='',
                )
                form = AddFilterForm(self.session, data)
                assert form.is_valid()

    def test_validation_ok_for_non_value_matches_with_number(self):
        non_value_match_types = [mt for mt, _ in FilterMatchType.ALL_DATA_TYPES_CHOICES]
        for match_type in non_value_match_types:
            with self.subTest(match_type=match_type):
                data = self._get_post_data(
                    'height',
                    DataType.INTEGER,
                    number_match_type=match_type,
                    number_value='',
                )
                form = AddFilterForm(self.session, data)
                assert form.is_valid()

    def test_validation_ok_for_non_value_matches_with_date(self):
        non_value_match_types = [mt for mt, _ in FilterMatchType.ALL_DATA_TYPES_CHOICES]
        for match_type in non_value_match_types:
            with self.subTest(match_type=match_type):
                data = self._get_post_data(
                    'watered_on',
                    DataType.DATE,
                    date_match_type=match_type,
                    date_value='',
                )
                form = AddFilterForm(self.session, data)
                assert form.is_valid()

    def test_validation_ok_for_non_value_matches_with_multi_select(self):
        non_value_match_types = [mt for mt, _ in FilterMatchType.ALL_DATA_TYPES_CHOICES]
        for match_type in non_value_match_types:
            with self.subTest(match_type=match_type):
                data = self._get_post_data(
                    'pot_type',
                    DataType.MULTIPLE_OPTION,
                    multi_select_match_type=match_type,
                    multi_select_value='',
                )
                form = AddFilterForm(self.session, data)
                assert form.is_valid()

    def test_validation_ok(self):
        cases = [
            ('soil_mix', DataType.TEXT, 'text_match_type', FilterMatchType.EXACT, 'text_value', 'chunky'),
            ('height', DataType.INTEGER, 'number_match_type', FilterMatchType.GREATER_THAN, 'number_value', '10'),
            (
                'watered_on',
                DataType.DATE,
                'date_match_type',
                FilterMatchType.LESS_THAN,
                'date_value',
                '2025-06-22',
            ),
            (
                'pot_type',
                DataType.MULTIPLE_OPTION,
                'multi_select_match_type',
                FilterMatchType.IS_ANY,
                'multi_select_value',
                ['ceramic', 'plastic'],
            ),
        ]
        for prop_id, data_type, match_field, match_type, value_field, value in cases:
            with self.subTest(prop_id=prop_id, data_type=data_type):
                data = self._get_post_data(
                    prop_id,
                    data_type,
                    **{
                        match_field: match_type,
                        value_field: value,
                    },
                )
                form = AddFilterForm(self.session, data)
                assert form.is_valid()
                assert form.cleaned_data['match_type'] == match_type
                if value_field == 'multi_select_value':
                    value = ' '.join(value)
                assert form.cleaned_data['value'] == value

    def test_validation_fails_bad_date_format(self):
        data = self._get_post_data(
            'watered_on',
            DataType.DATE,
            date_match_type=FilterMatchType.EXACT,
            date_value='not-a-date',
        )
        form = AddFilterForm(self.session, data)
        assert not form.is_valid()
        self.assertFormError(
            form,
            field='date_value',
            errors=["Date format should be 'YYYY-MM-DD'"],
        )

    def test_validation_fails_bad_datetime_format(self):
        data = self._get_post_data(
            'closed_on',
            DataType.DATETIME,
            date_match_type=FilterMatchType.EXACT,
            datetime_value='not-a-datetime',
        )
        form = AddFilterForm(self.session, data)
        assert not form.is_valid()
        self.assertFormError(
            form,
            field='datetime_value',
            errors=[
                "Date and Time format should be 'YYYY-MM-DD HH:MM:SS', "
                'where the hour is the 24-hour format, 00 to 23.'
            ],
        )

    def test_validation_fails_data_type_match_type_mismatch(self):
        data = self._get_post_data(
            'soil_mix',
            DataType.INTEGER,
            number_match_type=FilterMatchType.PHONETIC,
            number_value='chunk',
        )
        form = AddFilterForm(self.session, data)
        assert not form.is_valid()
        self.assertFormError(
            form,
            field='data_type',
            errors=['The selected data type cannot have the selected match type.'],
        )

    def test_validation_fails_when_text_contains_both_quotes(self):
        mt = FilterMatchType.EXACT
        bad = 'he said "don\'t"'
        data = self._get_post_data('soil_mix', DataType.TEXT, text_match_type=mt, text_value=bad)
        form = AddFilterForm(self.session, data)
        assert not form.is_valid()
        self.assertFormError(
            form,
            'text_value',
            ['This value cannot contain both single quotes (\') and double quotes (") at the same time.'],
        )

    def test_create_filter(self):
        assert not self.session.filters.filter(prop_id='soil_mix').exists()
        data = self._get_post_data(
            'soil_mix',
            DataType.TEXT,
            text_match_type=FilterMatchType.EXACT,
            text_value='chunky',
        )
        form = AddFilterForm(self.session, data)
        assert form.is_valid() is True
        form.create_filter()
        assert self.session.filters.filter(prop_id='soil_mix').exists()
        created_filter = self.session.filters.get(prop_id='soil_mix')
        assert created_filter.prop_id == 'soil_mix'
        assert created_filter.data_type == DataType.TEXT
        assert created_filter.match_type == FilterMatchType.EXACT
        assert created_filter.value == 'chunky'
