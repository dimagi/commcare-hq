from django.test import SimpleTestCase
from couchexport.transforms import couch_to_excel_datetime


class ExportTransformTest(SimpleTestCase):

    def test_couch_to_excel_datetime_current_fmt(self):
        self.assertEqual('2015-05-14 13:03:06', couch_to_excel_datetime('2015-05-14T13:03:06.455000Z', {}))

    def test_couch_to_excel_datetime_old_fmt(self):
        self.assertEqual('2014-10-07 12:27:15', couch_to_excel_datetime('2014-10-07T12:27:15Z', {}))
