import datetime
import pytz
from django.test import SimpleTestCase
from mock import patch

from corehq.apps.domain.models import Domain
from corehq.apps.export.forms import FilterFormESExportDownloadForm


class TestFilterFormESExportDownloadForm(SimpleTestCase):

    @patch('corehq.apps.reports.util.get_first_form_submission_received', lambda x: datetime.datetime(2015, 1, 1))
    def test_get_datespan_filter(self):
        form_data = {'date_range': '2015-06-25 to 2016-02-19'}
        form = FilterFormESExportDownloadForm(Domain(name="foo"), pytz.utc, form_data)
        self.assertTrue(form.is_valid())
        datespan_filter = form._get_datespan_filter()
        self.assertEqual(datespan_filter.lt, datetime.datetime(2016, 2, 20, tzinfo=pytz.utc))
        self.assertEqual(datespan_filter.gte, datetime.datetime(2015, 6, 25, tzinfo=pytz.utc))
        self.assertEqual(datespan_filter.lte, None)
        self.assertEqual(datespan_filter.gt, None)

    def test_get_group_filter(self):
        raise NotImplementedError

    @patch('corehq.apps.reports.util.get_first_form_submission_received', lambda x: datetime.datetime(2015, 1, 1))
    def test_get_user_filter(self):
        form_data = {'type_or_group': 'type', 'group': '', 'user_types': ['mobile', 'unknown']}
        form = FilterFormESExportDownloadForm(Domain(name="foo"), pytz.utc, form_data)
        self.assertTrue(form.is_valid())
        raise NotImplementedError

