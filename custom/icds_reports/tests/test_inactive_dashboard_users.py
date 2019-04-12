from __future__ import absolute_import

from __future__ import unicode_literals
from django.test.testcases import TestCase
from django.test.client import RequestFactory
from django.core.urlresolvers import reverse
from custom.icds_reports.tasks import  collect_inactive_dashboard_users
from custom.icds_reports.models.helper import IcdsFile
import json
import mock
import datetime
import zipfile
import csv
class Base(TestCase):

    def setUp(self):
        self.factory = None
        self.user = None
        self.view = None
        self.url = None
        self.run_july_third_test = False

    def test_get_inactive_users(self):
        IcdsFile.objects.filter(data_type='inactive_dashboard_users').all().delete()
        collect_inactive_dashboard_users()
        sync = IcdsFile.objects.filter(data_type='inactive_dashboard_users').order_by('-file_added').first()
        with sync.get_file_from_blobdb() as fileobj:
            zip = zipfile.ZipFile(fileobj, 'r')
            for zipped_file in zip.namelist():
                csv_reader = csv.reader(zip.open(zipped_file))
                data = list(csv_reader)

                self.assertEqual([['Username', 'Location', 'State']], data)

    def test_get_inactive_users_data_Added(self):
        from corehq.apps.locations.models import LocationType, SQLLocation

        from corehq.apps.users.models import CommCareUser
        CommCareUser(domain='icds-cas', username='123.testing@icds-cas.commcare.org').save()
        CommCareUser(domain='icds-cas', username='234.testing@icds-cas.commcare.org').save()
        IcdsFile.objects.filter(data_type='inactive_dashboard_users').all().delete()
        collect_inactive_dashboard_users()
        sync = IcdsFile.objects.filter(data_type='inactive_dashboard_users').order_by('-file_added').first()
        with sync.get_file_from_blobdb() as fileobj:
            zip = zipfile.ZipFile(fileobj, 'r')
            for zipped_file in zip.namelist():
                csv_reader = csv.reader(zip.open(zipped_file), )
                data = list(csv_reader)
                sorted(data, key=lambda x: x[0])
                self.assertEqual([['Username', 'Location', 'State'],
                                  ['234.testing@icds-cas.commcare.org', '', ''],
                                  ['123.testing@icds-cas.commcare.org', '', '']
                                  ], data)