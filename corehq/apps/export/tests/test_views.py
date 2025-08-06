from unittest.mock import patch

from django.test import TestCase

from corehq import toggles
from corehq.apps.data_dictionary.models import CaseProperty, CaseType
from corehq.apps.domain.models import Domain
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.export.const import (
    ALL_CASE_TYPE_EXPORT,
    CASE_EXPORT,
    FORM_EXPORT,
)
from corehq.apps.export.models.new import (
    CaseExportInstance,
    ExportColumn,
    FormExportInstance,
    GeopointItem,
    PathNode,
    ScalarItem,
    TableConfiguration,
)
from corehq.apps.export.views.new import BaseExportView
from corehq.util.test_utils import flag_enabled

DOMAIN = 'test-domain'


class TestableBaseExportView(BaseExportView):
    """
    Testable implementation of BaseExportView
    """
    __test__ = False

    export_type = None

    def __init__(self, export_instance):
        super().__init__()
        self.export_instance = export_instance
        self.args = [export_instance.domain]

    @property
    def export_helper(self):
        return None


class BaseExportViewTestCase(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain_obj = create_domain(DOMAIN)
        cls.addClassCleanup(cls.domain_obj.delete)

        cls.case_type = CaseType.objects.create(
            domain=cls.domain_obj.name,
            name='test_case_type'
        )
        cls.gps_property1 = CaseProperty.objects.create(
            case_type=cls.case_type,
            name='location_gps',
            data_type=CaseProperty.DataType.GPS
        )
        cls.gps_property2 = CaseProperty.objects.create(
            case_type=cls.case_type,
            name='home_location',
            data_type=CaseProperty.DataType.GPS
        )
        cls.text_property = CaseProperty.objects.create(
            case_type=cls.case_type,
            name='name',
            data_type=CaseProperty.DataType.PLAIN
        )

    def _create_form_export_instance_with_geopoint(self):
        from corehq.apps.export.models.new import ScalarItem

        geopoint_item = GeopointItem(
            path=[
                PathNode(name='form'),
                PathNode(name='location'),
                PathNode(name='gps_coords')
            ]
        )
        geopoint_item2 = GeopointItem(
            path=[
                PathNode(name='form'),
                PathNode(name='user_location')
            ]
        )
        text_item = ScalarItem(
            path=[
                PathNode(name='form'),
                PathNode(name='name')
            ]
        )
        geo_column1 = ExportColumn(
            label='GPS Coordinates',
            item=geopoint_item,
            selected=True
        )
        geo_column2 = ExportColumn(
            label='User Location',
            item=geopoint_item2,
            selected=True
        )
        text_column = ExportColumn(
            label='Name',
            item=text_item,
            selected=True
        )
        table_config = TableConfiguration(
            label='Forms',
            selected=True,
            columns=[geo_column1, geo_column2, text_column]
        )
        export_instance = FormExportInstance(
            domain=DOMAIN,
            name='Test Form Export',
            xmlns='test_xmlns',
            tables=[table_config]
        )
        return export_instance

    def _create_case_export_instance(self):
        table_config = TableConfiguration(
            label='Cases',
            selected=True,
            columns=[]
        )
        export_instance = CaseExportInstance(
            domain=DOMAIN,
            name='Test Case Export',
            case_type='test_case_type',
            tables=[table_config]
        )
        return export_instance


class TestPossibleGeoProperties(BaseExportViewTestCase):

    def test_possible_geo_properties_toggle_disabled(self):
        """
        Test that _possible_geo_properties returns empty list when
        toggle is disabled
        """
        export_instance = self._create_form_export_instance_with_geopoint()
        view = TestableBaseExportView(export_instance)
        view.export_type = FORM_EXPORT
        with patch.object(toggles.SUPPORT_GEO_JSON_EXPORT, 'enabled') as mock_toggle:
            mock_toggle.return_value = False

            result = view._possible_geo_properties
            self.assertEqual(result, [])

    @flag_enabled('SUPPORT_GEO_JSON_EXPORT')
    def test_possible_geo_properties_bulk_case_export(self):
        """
        Test that _possible_geo_properties returns empty list for bulk
        case export
        """
        bulk_case_export_instance = CaseExportInstance(
            domain=DOMAIN,
            name='Test Bulk Case Export',
            case_type=ALL_CASE_TYPE_EXPORT,
            tables=[]
        )
        view = TestableBaseExportView(bulk_case_export_instance)
        view.export_type = CASE_EXPORT

        result = view._possible_geo_properties
        self.assertEqual(result, [])

    @flag_enabled('SUPPORT_GEO_JSON_EXPORT')
    def test_possible_geo_properties_form_export(self):
        """
        Test that _possible_geo_properties calls
        _possible_form_geo_properties for form exports
        """
        export_instance = self._create_form_export_instance_with_geopoint()
        view = TestableBaseExportView(export_instance)
        view.export_type = FORM_EXPORT

        result = view._possible_geo_properties
        expected = ['form.location.gps_coords', 'form.user_location']
        self.assertEqual(result, expected)

    @flag_enabled('SUPPORT_GEO_JSON_EXPORT')
    def test_possible_geo_properties_case_export(self):
        """
        Test that _possible_geo_properties calls
        _possible_case_geo_properties for case exports
        """
        export_instance = self._create_case_export_instance()
        view = TestableBaseExportView(export_instance)
        view.export_type = CASE_EXPORT

        result = view._possible_geo_properties
        expected = ['location_gps', 'home_location']
        self.assertEqual(sorted(result), sorted(expected))


class TestPossibleFormGeoProperties(BaseExportViewTestCase):

    def test_possible_form_geo_properties_with_geopoint_items(self):
        """
        Test that _possible_form_geo_properties returns paths for
        GeopointItem columns
        """
        export_instance = self._create_form_export_instance_with_geopoint()
        view = TestableBaseExportView(export_instance)

        result = view._possible_form_geo_properties
        expected = ['form.location.gps_coords', 'form.user_location']
        self.assertEqual(result, expected)

    def test_possible_form_geo_properties_no_geopoint_items(self):
        """
        Test that _possible_form_geo_properties returns empty list when
        no GeopointItem columns
        """
        text_item = ScalarItem(
            path=[PathNode(name='form'), PathNode(name='name')]
        )
        text_column = ExportColumn(
            label='Name',
            item=text_item,
            selected=True
        )
        table_config = TableConfiguration(
            label='Forms',
            selected=True,
            columns=[text_column]
        )
        export_instance = FormExportInstance(
            domain=DOMAIN,
            name='Test Form Export',
            xmlns='test_xmlns',
            tables=[table_config]
        )
        view = TestableBaseExportView(export_instance)

        result = view._possible_form_geo_properties
        self.assertEqual(result, [])

    def test_possible_form_geo_properties_empty_tables(self):
        """
        Test that _possible_form_geo_properties handles empty tables
        gracefully
        """
        export_instance = FormExportInstance(
            domain=DOMAIN,
            name='Test Form Export',
            xmlns='test_xmlns',
            tables=[]
        )
        view = TestableBaseExportView(export_instance)

        with self.assertRaises(IndexError):
            view._possible_form_geo_properties


class TestPossibleCaseGeoProperties(BaseExportViewTestCase):

    def test_possible_case_geo_properties_with_gps_properties(self):
        """
        Test that _possible_case_geo_properties returns GPS case
        properties
        """
        export_instance = self._create_case_export_instance()
        view = TestableBaseExportView(export_instance)

        result = view._possible_case_geo_properties
        expected = ['location_gps', 'home_location']
        self.assertEqual(sorted(result), sorted(expected))

    def test_possible_case_geo_properties_no_gps_properties(self):
        """
        Test that _possible_case_geo_properties returns empty list when
        no GPS properties
        """
        case_type_no_gps = CaseType.objects.create(
            domain=DOMAIN,
            name='no_gps_case_type'
        )
        CaseProperty.objects.create(
            case_type=case_type_no_gps,
            name='name',
            data_type=CaseProperty.DataType.PLAIN
        )
        export_instance = CaseExportInstance(
            domain=DOMAIN,
            name='Test Case Export',
            case_type='no_gps_case_type',
            tables=[]
        )
        view = TestableBaseExportView(export_instance)

        result = view._possible_case_geo_properties
        self.assertEqual(result, [])

    def test_possible_case_geo_properties_different_domain(self):
        """
        Test that _possible_case_geo_properties only returns properties
        for the correct domain
        """
        other_domain = Domain(name='other-domain', is_active=True)
        other_domain.save()
        self.addCleanup(other_domain.delete)

        other_case_type = CaseType.objects.create(
            domain='other-domain',
            name='test_case_type'
        )
        CaseProperty.objects.create(
            case_type=other_case_type,
            name='other_location',
            data_type=CaseProperty.DataType.GPS
        )
        export_instance = self._create_case_export_instance()
        view = TestableBaseExportView(export_instance)

        result = view._possible_case_geo_properties
        expected = ['location_gps', 'home_location']
        self.assertEqual(sorted(result), sorted(expected))
        self.assertNotIn('other_location', result)
