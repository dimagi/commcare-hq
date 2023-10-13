from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase, TestCase

from nose.tools import assert_equal

from corehq.apps.data_dictionary.models import CaseProperty, CaseType
from corehq.motech.fhir.models import FHIRResourceProperty, FHIRResourceType
from corehq.motech.fhir.utils import (
    load_fhir_resource_types,
    resource_url,
    update_fhir_resource_property,
    validate_accept_header_and_format_param,
    require_fhir_json_content_type_headers
)

DOMAIN = "test-domain"


class TestUpdateFHIRResourceProperty(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.case_type = CaseType.objects.create(
            domain=DOMAIN,
            name='person',
        )
        cls.case_property = CaseProperty.objects.create(
            case_type=cls.case_type,
            name='name',
        )
        cls.resource_type = FHIRResourceType.objects.create(
            domain=DOMAIN,
            case_type=cls.case_type,
        )

    @classmethod
    def tearDownClass(cls):
        cls.resource_type.delete()
        cls.case_property.delete()
        cls.case_type.delete()
        super().tearDownClass()

    def test_delete_if_deprecated(self):
        old_deprecated_value = self.case_property.deprecated
        self.case_property.deprecated = True
        fhir_resource_prop_path = "$.name[0].text"

        # when no resource property mapped
        self.assertEqual(
            FHIRResourceProperty.objects.filter(
                resource_type=self.resource_type,
                case_property=self.case_property,
                jsonpath=fhir_resource_prop_path
            ).count(),
            0)
        update_fhir_resource_property(self.case_property, self.resource_type, fhir_resource_prop_path)

        # when resource property present
        fhir_resource_prop = FHIRResourceProperty.objects.create(
            resource_type=self.resource_type,
            case_property=self.case_property,
            jsonpath=fhir_resource_prop_path
        )
        self.addCleanup(fhir_resource_prop.delete)

        update_fhir_resource_property(self.case_property, self.resource_type, fhir_resource_prop_path)
        self.assertEqual(
            FHIRResourceProperty.objects.filter(
                resource_type=self.resource_type,
                case_property=self.case_property,
                jsonpath=fhir_resource_prop_path
            ).count(),
            0)

        # reset
        self.case_property.deprecated = old_deprecated_value

    def test_delete_if_to_be_removed(self):
        fhir_resource_prop_path = "$.name[0].text"

        # when no resource property mapped
        self.assertEqual(
            FHIRResourceProperty.objects.filter(
                resource_type=self.resource_type,
                case_property=self.case_property,
                jsonpath=fhir_resource_prop_path
            ).count(),
            0)
        update_fhir_resource_property(self.case_property, self.resource_type, fhir_resource_prop_path, True)

        # when resource property present
        fhir_resource_prop = FHIRResourceProperty.objects.create(
            resource_type=self.resource_type,
            case_property=self.case_property,
            jsonpath=fhir_resource_prop_path
        )
        self.addCleanup(fhir_resource_prop.delete)

        update_fhir_resource_property(self.case_property, self.resource_type, fhir_resource_prop_path, True)
        self.assertEqual(
            FHIRResourceProperty.objects.filter(
                resource_type=self.resource_type,
                case_property=self.case_property,
                jsonpath=fhir_resource_prop_path
            ).count(),
            0)

    def test_simply_update(self):
        fhir_resource_prop_path = "$.name[0].text"

        # when no resource property mapped
        self.assertEqual(
            FHIRResourceProperty.objects.filter(
                resource_type=self.resource_type,
                case_property=self.case_property,
                jsonpath=fhir_resource_prop_path
            ).count(),
            0)
        update_fhir_resource_property(self.case_property, self.resource_type, fhir_resource_prop_path)
        self.assertEqual(
            FHIRResourceProperty.objects.filter(
                resource_type=self.resource_type,
                case_property=self.case_property,
                jsonpath=fhir_resource_prop_path
            ).count(),
            1)

        # when resource property present
        new_fhir_resource_prop_path = "$.age[0].text"
        update_fhir_resource_property(self.case_property, self.resource_type, new_fhir_resource_prop_path)
        self.assertEqual(
            FHIRResourceProperty.objects.filter(
                resource_type=self.resource_type,
                case_property=self.case_property,
                jsonpath=fhir_resource_prop_path
            ).count(),
            0)
        self.assertEqual(
            FHIRResourceProperty.objects.filter(
                resource_type=self.resource_type,
                case_property=self.case_property,
                jsonpath=new_fhir_resource_prop_path
            ).count(),
            1)


class TestLoadFHIRResourceType(SimpleTestCase):

    def test_load_fhir_resource_types_default(self):
        resource_types = load_fhir_resource_types()
        self.assertIsInstance(resource_types, list)
        self.assertTrue('fhir' not in resource_types)


def test_resource_url():
    url = resource_url(DOMAIN, 'R4', 'Patient', 'abc123')
    drop_hostname = url.split('/', maxsplit=3)[3]
    assert_equal(drop_hostname, f'a/{DOMAIN}/fhir/R4/Patient/abc123/')


class TestHeaderDecorators(TestCase):

    def setUp(self):
        self.factory = RequestFactory()

    def _do_get_request(self, view, params=None, headers={}):
        request = self.factory.get('/foo', params, **headers)
        return view(request)

    def test_validate_format_param(self):
        @validate_accept_header_and_format_param
        def test_view(request):
            return HttpResponse()
        response = self._do_get_request(test_view)
        self.assertEqual(response.status_code, 200)
        response = self._do_get_request(test_view, {'_format': 'application/json'})
        self.assertEqual(response.status_code, 200)
        response = self._do_get_request(test_view, {'_format': 'application/xml'})
        self.assertEqual(response.status_code, 406)
        self.assertEqual(
            response.content.decode("utf-8"),
            '{"message": "Requested format in \'_format\' param not acceptable."}'
        )
        response = test_view(self.factory.post('/foo', {'_format': 'application/xml'}))
        self.assertEqual(response.status_code, 406)

    def test_validate_accept_header(self):
        @validate_accept_header_and_format_param
        def test_view(request):
            return HttpResponse()
        response = self._do_get_request(test_view)
        self.assertEqual(response.status_code, 200)
        response = self._do_get_request(test_view, headers={'HTTP_ACCEPT': 'application/json'})
        self.assertEqual(response.status_code, 200)
        response = self._do_get_request(test_view, headers={'HTTP_ACCEPT': 'application/xml'})
        self.assertEqual(response.status_code, 406)
        self.assertEqual(
            response.content.decode("utf-8"),
            '{"message": "Not Acceptable"}'
        )

    def test_format_param_overwrites_accept_header(self):
        @validate_accept_header_and_format_param
        def test_view(request):
            return HttpResponse()
        response = self._do_get_request(test_view, {'_format': 'application/xml'},
                                        headers={'HTTP_ACCEPT': 'application/json'})
        self.assertEqual(response.status_code, 406)

    def _do_post_request(self, view, content_type=None):
        request = self.factory.post('/foo', content_type=content_type)
        return view(request)

    def test_require_fhir_json_content_type_headers(self):
        @require_fhir_json_content_type_headers
        def test_view(request):
            return HttpResponse()
        response = self._do_post_request(test_view, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        response = self._do_post_request(test_view, content_type='application/xml')
        self.assertEqual(response.status_code, 415)
        self.assertEqual(
            response.content.decode("utf-8"),
            '{"message": "Unsupported Media Type"}'
        )
