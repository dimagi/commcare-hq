from django.test import TestCase

from corehq.apps.data_cleaning.forms.bulk_edit import EditSelectedRecordsForm
from corehq.apps.data_cleaning.models.session import BulkEditSession
from corehq.apps.data_cleaning.models.types import DataType, EditActionType
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.models import WebUser
from corehq.util.test_utils import disable_quickcache


@disable_quickcache
class TestEditSelectedRecordsForm(TestCase):
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

    def setUp(self):
        super().setUp()
        self.session = BulkEditSession.objects.new_case_session(
            self.web_user.get_django_user(),
            self.domain,
            self.case_type,
        )
        self.session.add_column('soil_mix', 'Soil Mix', DataType.TEXT)
        self.session.add_column('height', 'Height', DataType.INTEGER)
        self.session.add_column('height_cm', 'Height (cm)', DataType.INTEGER)

    @staticmethod
    def _get_post_data(
        prop_id,
        action,
        find_string=None,
        use_regex=False,
        replace_string=None,
        replace_all_string=None,
        copy_from_prop_id=None,
    ):
        return {
            'edit_prop_id': prop_id,
            'edit_action': action,
            'find_string': find_string,
            'use_regex': ['on'] if use_regex else None,
            'replace_string': replace_string,
            'replace_all_string': replace_all_string,
            'copy_from_prop_id': copy_from_prop_id,
        }

    def test_form_is_visible(self):
        form = EditSelectedRecordsForm(self.session)
        assert form.is_form_visible

    def test_form_is_not_visible(self):
        self.session.columns.filter(is_system=False).all().delete()
        form = EditSelectedRecordsForm(self.session)
        assert not form.is_form_visible

    def test_validation_fails_uneditable_property(self):
        data = self._get_post_data('closed_on', EditActionType.REPLACE)
        form = EditSelectedRecordsForm(self.session, data)
        assert not form.is_valid()
        self.assertFormError(
            form,
            field='edit_prop_id',
            errors=['Select a valid choice. closed_on is not one of the available choices.'],
        )

    def test_validation_fails_replace_without_value(self):
        data = self._get_post_data('soil_mix', EditActionType.REPLACE)
        form = EditSelectedRecordsForm(self.session, data)
        assert not form.is_valid()
        self.assertFormError(
            form,
            field='replace_all_string',
            errors=['Please specify a value you would like to replace the existing property value with.'],
        )

    def test_validation_ok_replace_with_value(self):
        data = self._get_post_data('soil_mix', EditActionType.REPLACE, replace_all_string='chunky')
        form = EditSelectedRecordsForm(self.session, data)
        assert form.is_valid()

    def test_validation_fails_find_without_value(self):
        data = self._get_post_data('soil_mix', EditActionType.FIND_REPLACE)
        form = EditSelectedRecordsForm(self.session, data)
        assert not form.is_valid()
        self.assertFormError(
            form,
            field='find_string',
            errors=['Please specify the value you would like to find.'],
        )

    def test_validation_ok_find_with_value(self):
        data = self._get_post_data('soil_mix', EditActionType.FIND_REPLACE, find_string='chunky')
        form = EditSelectedRecordsForm(self.session, data)
        assert form.is_valid()

    def test_validation_fails_find_with_invalid_regex(self):
        data = self._get_post_data('soil_mix', EditActionType.FIND_REPLACE, find_string='[unclosed')
        form = EditSelectedRecordsForm(self.session, data)
        assert not form.is_valid()
        self.assertFormError(
            form,
            field='find_string',
            errors=['Not a valid regular expression.'],
        )

    def test_validation_ok_find_with_valid_regex(self):
        data = self._get_post_data('soil_mix', EditActionType.FIND_REPLACE, find_string='chunky.*')
        form = EditSelectedRecordsForm(self.session, data)
        assert form.is_valid()

    def test_validation_fails_copy_from_prop_id_not_selected(self):
        data = self._get_post_data('height', EditActionType.COPY_REPLACE)
        form = EditSelectedRecordsForm(self.session, data)
        assert not form.is_valid()
        self.assertFormError(
            form,
            field='copy_from_prop_id',
            errors=['Please select a property to copy from.'],
        )

    def test_validation_fails_copy_from_prop_id_same_as_edit_prop_id(self):
        data = self._get_post_data('height', EditActionType.COPY_REPLACE, copy_from_prop_id='height')
        form = EditSelectedRecordsForm(self.session, data)
        assert not form.is_valid()
        self.assertFormError(
            form,
            field='copy_from_prop_id',
            errors=['You cannot copy from the same property.'],
        )

    def test_validation_ok_copy_from_prop_id_different_from_edit_prop_id(self):
        data = self._get_post_data('height', EditActionType.COPY_REPLACE, copy_from_prop_id='height_cm')
        form = EditSelectedRecordsForm(self.session, data)
        assert form.is_valid()

    def test_get_bulk_edit_change_replace(self):
        data = self._get_post_data('soil_mix', EditActionType.REPLACE, replace_all_string='chunky')
        form = EditSelectedRecordsForm(self.session, data)
        assert form.is_valid()
        change = form.get_bulk_edit_change()
        assert change.prop_id == 'soil_mix'
        assert change.action_type == EditActionType.REPLACE
        assert change.replace_string == 'chunky'

    def test_get_bulk_edit_change_find_replace(self):
        data = self._get_post_data(
            'soil_mix',
            EditActionType.FIND_REPLACE,
            find_string='chunky.*',
            replace_string='creamy',
            use_regex=True,
        )
        form = EditSelectedRecordsForm(self.session, data)
        assert form.is_valid()
        change = form.get_bulk_edit_change()
        assert change.prop_id == 'soil_mix'
        assert change.action_type == EditActionType.FIND_REPLACE
        assert change.find_string == 'chunky.*'
        assert change.replace_string == 'creamy'
        assert change.use_regex

    def test_get_bulk_edit_change_copy_replace(self):
        data = self._get_post_data('height', EditActionType.COPY_REPLACE, copy_from_prop_id='height_cm')
        form = EditSelectedRecordsForm(self.session, data)
        assert form.is_valid()
        change = form.get_bulk_edit_change()
        assert change.prop_id == 'height'
        assert change.action_type == EditActionType.COPY_REPLACE
        assert change.copy_from_prop_id == 'height_cm'
