import datetime
from collections import namedtuple

import pytz
from django.test import SimpleTestCase
from mock import patch

from corehq.apps.export.filters import FormSubmittedByFilter
from corehq.apps.export.forms import FilterFormESExportDownloadForm


class TestFilterFormESExportDownloadForm(SimpleTestCase):

    def setUp(self):
        DomainObject = namedtuple('DomainObject', ['uses_locations', 'name', 'date_created'])
        self.project = DomainObject(False, "foo", datetime.datetime(2015, 1, 1))

    def test_get_datespan_filter(self):
        form_data = {'date_range': '2015-06-25 to 2016-02-19'}
        form = FilterFormESExportDownloadForm(self.project, pytz.utc, form_data)
        self.assertTrue(form.is_valid())
        datespan_filter = form._get_datespan_filter()
        self.assertEqual(datespan_filter.lt, datetime.datetime(2016, 2, 20, tzinfo=pytz.utc))
        self.assertEqual(datespan_filter.gte, datetime.datetime(2015, 6, 25, tzinfo=pytz.utc))
        self.assertEqual(datespan_filter.lte, None)
        self.assertEqual(datespan_filter.gt, None)

    def test_get_group_filter(self):
        """
        Confirm that FilterFormESExportDownloadForm._get_group_filter() returns
        a filter with the correct group_id and correct base_filter.
        """
        form_data = {
            'type_or_group': 'group',
            'group': 'some_group_id',
            'date_range': '2015-06-25 to 2016-02-19',
        }
        form = FilterFormESExportDownloadForm(self.project, pytz.utc, form_data)
        self.assertTrue(form.is_valid(), "Form had the following errors: {}".format(form.errors))
        group_filter = form._get_group_filter()
        self.assertEqual(group_filter.group_id, 'some_group_id')
        self.assertEqual(group_filter.base_filter, FormSubmittedByFilter)
