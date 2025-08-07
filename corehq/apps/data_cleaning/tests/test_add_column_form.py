from unittest import mock

from django.test import TestCase

from corehq.apps.data_cleaning.forms.columns import AddColumnForm
from corehq.apps.data_cleaning.models.session import BulkEditSession
from corehq.apps.data_cleaning.models.types import DataType
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.models import WebUser
from corehq.util.test_utils import disable_quickcache


@disable_quickcache
class TestAddColumnForm(TestCase):
    domain = 'dc-add-column-form-test'
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
    def _get_post_data(prop_id, label, data_type):
        return {
            'column_prop_id': prop_id,
            'column_label': label,
            'column_data_type': data_type,
        }

    def test_validation_fails_column_prop_id_is_required(self):
        data = self._get_post_data('', 'Test', DataType.TEXT)
        form = AddColumnForm(self.session, data)
        assert not form.is_valid()
        self.assertFormError(
            form,
            field='column_prop_id',
            errors=['Please specify a case property.']
        )

    def test_validation_ok_new_property(self):
        data = self._get_post_data('soil_mix', 'Soil Mix', DataType.TEXT)
        form = AddColumnForm(self.session, data)
        assert form.is_valid()

    def test_form_add_column(self):
        data = self._get_post_data('soil_mix', 'Soil Mix', DataType.TEXT)
        form = AddColumnForm(self.session, data)
        form.is_valid()
        form.add_column()
        assert self.session.columns.filter(prop_id='soil_mix').exists()
        created_column = self.session.columns.get(prop_id='soil_mix')
        assert created_column.prop_id == 'soil_mix'
        assert created_column.label == 'Soil Mix'
        assert created_column.data_type == DataType.TEXT

    def test_validation_fails_column_prop_id_exists(self):
        self.session.add_column('soil_mix', 'Soil Mixture', DataType.TEXT)
        data = self._get_post_data('soil_mix', 'Soil Mix', DataType.TEXT)
        form = AddColumnForm(self.session, data)
        assert not form.is_valid()
        self.assertFormError(
            form,
            field='column_prop_id',
            errors=['Select a valid choice. soil_mix is not one of the available choices.']
        )

    def test_validation_fails_column_data_type_is_required(self):
        data = self._get_post_data('soil_mix', 'Soil Mix', '')
        form = AddColumnForm(self.session, data)
        assert not form.is_valid()
        self.assertFormError(
            form,
            field='column_data_type',
            errors=['Please specify a data type.']
        )

    def test_validation_fails_column_label_is_required(self):
        data = self._get_post_data('soil_mix', '', DataType.TEXT)
        form = AddColumnForm(self.session, data)
        assert not form.is_valid()
        self.assertFormError(
            form,
            field='column_label',
            errors=['Please specify a label for the column.']
        )

    def test_validation_fails_system_property_incorrect_type(self):
        data = self._get_post_data('closed_on', 'Closed On', DataType.TEXT)
        form = AddColumnForm(self.session, data)
        assert not form.is_valid()
        self.assertFormError(
            form,
            field='column_data_type',
            errors=[f"Incorrect data type for 'closed_on', should be '{DataType.DATETIME}'"]
        )

    def test_validation_ok_system_property_correct_type(self):
        data = self._get_post_data('closed_on', 'Closed On', DataType.DATETIME)
        form = AddColumnForm(self.session, data)
        assert form.is_valid()
