from django.test import SimpleTestCase

from corehq.apps.export.models.new import SplitGPSExportColumn


class GPSCoordinateTests(SimpleTestCase):
    def test_no_coords_returns_array_of_empty_strings(self):
        coord_array = SplitGPSExportColumn.extract_coordinate_array(None)

        self.assertEqual(coord_array, ['', '', '', ''])

    def test_coord_missing_value_returns_array_of_missing_values(self):
        coord_array = SplitGPSExportColumn.extract_coordinate_array('---')

        self.assertEqual(coord_array, ['---', '---', '---', '---'])

    def test_empty_values_are_added_to_lat_lng(self):
        coord_string = '1.0 2.0'
        coord_array = SplitGPSExportColumn.extract_coordinate_array(coord_string)

        self.assertEqual(coord_array, ['1.0', '2.0', '', ''])

    def test_extra_values_are_ignored(self):
        coord_string = '1.0 2.0 3.0 4.0 5.0'
        coord_array = SplitGPSExportColumn.extract_coordinate_array(coord_string)

        self.assertEqual(coord_array, ['1.0', '2.0', '3.0', '4.0'])

    def test_leading_spaces_are_ignored(self):
        coord_string = ' 1.0 2.0 3.0 4.0'
        coord_array = SplitGPSExportColumn.extract_coordinate_array(coord_string)

        self.assertEqual(coord_array, ['1.0', '2.0', '3.0', '4.0'])

    def test_trailing_spaces_are_ignored(self):
        coord_string = '1.0 2.0 3.0 4.0 '
        coord_array = SplitGPSExportColumn.extract_coordinate_array(coord_string)

        self.assertEqual(coord_array, ['1.0', '2.0', '3.0', '4.0'])

    def test_multiple_spaces_are_treated_as_one_separator(self):
        coord_string = '1.0     2.0 3.0 4.0'
        coord_array = SplitGPSExportColumn.extract_coordinate_array(coord_string)

        self.assertEqual(coord_array, ['1.0', '2.0', '3.0', '4.0'])
