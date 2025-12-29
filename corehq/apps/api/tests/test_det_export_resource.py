from unittest.mock import patch

from corehq.apps.api.resources import v1_0
from corehq.apps.export.models import CaseExportInstance, FormExportInstance

from .utils import APIResourceTest


def _noop(*args, **kwargs):
    pass


class TestDETExportInstanceResource(APIResourceTest):
    resource = v1_0.DETExportInstanceResource
    api_name = 'v1'

    @classmethod
    def setUpClass(cls):
        with patch('corehq.apps.accounting.models.publish_domain_saved', _noop):
            super().setUpClass()

        cls.form_export_visible = FormExportInstance(
            domain=cls.domain.name,
            name='Form Export Visible',
            xmlns='http://example.com/form1',
            show_det_config_download=True,
            export_format='xlsx'
        )
        cls.form_export_visible.save()

        cls.form_export_hidden = FormExportInstance(
            domain=cls.domain.name,
            name='Form Export Hidden',
            xmlns='http://example.com/form2',
            show_det_config_download=False,
            export_format='xlsx'
        )
        cls.form_export_hidden.save()

        cls.case_export_visible = CaseExportInstance(
            domain=cls.domain.name,
            name='Case Export Visible',
            case_type='person',
            show_det_config_download=True,
            export_format='csv'
        )
        cls.case_export_visible.save()

        cls.case_export_hidden = CaseExportInstance(
            domain=cls.domain.name,
            name='Case Export Hidden',
            case_type='household',
            show_det_config_download=False,
            export_format='csv'
        )
        cls.case_export_hidden.save()

    @classmethod
    def tearDownClass(cls):
        cls.form_export_visible.delete()
        cls.form_export_hidden.delete()
        cls.case_export_visible.delete()
        cls.case_export_hidden.delete()
        with patch('corehq.apps.accounting.models.publish_domain_saved', _noop):
            super().tearDownClass()

    def _get_list_objects(self):
        response = self._assert_auth_get_resource(self.list_endpoint)
        assert response.status_code == 200
        data = response.json()
        return data.get('objects', [])

    def test_get_list_only_shows_det_exports(self):
        objects = self._get_list_objects()
        returned_ids = {obj['id'] for obj in objects}

        assert len(objects) == 2
        assert self.form_export_visible._id in returned_ids
        assert self.case_export_visible._id in returned_ids
        assert self.form_export_hidden._id not in returned_ids
        assert self.case_export_hidden._id not in returned_ids

    def test_get_list_returns_correct_form_export_fields(self):
        objects = self._get_list_objects()
        form_export_obj = next(
            (obj for obj in objects if obj['id'] == self.form_export_visible._id),
            None
        )
        assert form_export_obj is not None
        assert form_export_obj['name'] == 'Form Export Visible'
        assert form_export_obj['type'] == 'form'
        assert form_export_obj['export_format'] == 'xlsx'
        assert form_export_obj['xmlns'] == 'http://example.com/form1'
        assert form_export_obj['case_type'] is None
        assert self.form_export_visible._id in form_export_obj['det_config_url']

    def test_get_list_returns_correct_case_export_fields(self):
        objects = self._get_list_objects()
        case_export_obj = next(
            (obj for obj in objects if obj['id'] == self.case_export_visible._id),
            None
        )
        assert case_export_obj is not None
        assert case_export_obj['name'] == 'Case Export Visible'
        assert case_export_obj['type'] == 'case'
        assert case_export_obj['export_format'] == 'csv'
        assert case_export_obj['case_type'] == 'person'
        assert case_export_obj['xmlns'] is None
        assert self.case_export_visible._id in case_export_obj['det_config_url']

    def test_get_detail_for_form_export(self):
        detail_url = self.single_endpoint(self.form_export_visible._id)
        response = self._assert_auth_get_resource(detail_url)
        assert response.status_code == 200

        data = response.json()
        assert data['id'] == self.form_export_visible._id
        assert data['name'] == 'Form Export Visible'
        assert data['type'] == 'form'
        assert self.form_export_visible._id in data['det_config_url']

    def test_get_detail_for_case_export(self):
        detail_url = self.single_endpoint(self.case_export_visible._id)
        response = self._assert_auth_get_resource(detail_url)
        assert response.status_code == 200

        data = response.json()
        assert data['id'] == self.case_export_visible._id
        assert data['name'] == 'Case Export Visible'
        assert data['type'] == 'case'
        assert self.case_export_visible._id in data['det_config_url']

    def test_get_detail_for_hidden_export_returns_404(self):
        detail_url = self.single_endpoint(self.form_export_hidden._id)
        response = self._assert_auth_get_resource(detail_url)
        assert response.status_code == 404
