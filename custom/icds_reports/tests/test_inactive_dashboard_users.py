from __future__ import absolute_import
from __future__ import unicode_literals

import zipfile
import csv342 as csv
import io

from django.test.testcases import TestCase
from custom.icds_reports.tasks import collect_inactive_dashboard_users
from custom.icds_reports.models.helper import IcdsFile
from corehq.apps.users.models import CommCareUser


class TestInactiveMobileUsers(TestCase):

    def test_get_inactive_users(self):
        IcdsFile.objects.filter(data_type='inactive_dashboard_users').all().delete()
        collect_inactive_dashboard_users()
        sync = IcdsFile.objects.filter(data_type='inactive_dashboard_users').order_by('-file_added').first()
        with sync.get_file_from_blobdb() as fileobj:
            zip = zipfile.ZipFile(fileobj, 'r')
            for zipped_file in zip.namelist():
                items_file = zip.open(zipped_file)
                items_file = io.TextIOWrapper(io.BytesIO(items_file.read()))
                csv_reader = csv.reader(items_file)
                data = list(csv_reader)

                self.assertEqual([['Username', 'Location', 'State']], data)

    def test_get_inactive_users_data_added(self):
        CommCareUser(domain='icds-cas', username='123.testing@icds-cas.commcare.org').save()
        CommCareUser(domain='icds-cas', username='234.testing@icds-cas.commcare.org').save()
        IcdsFile.objects.filter(data_type='inactive_dashboard_users').all().delete()
        collect_inactive_dashboard_users()
        sync = IcdsFile.objects.filter(data_type='inactive_dashboard_users').order_by('-file_added').first()
        with sync.get_file_from_blobdb() as fileobj:
            zip = zipfile.ZipFile(fileobj, 'r')
            for zipped_file in zip.namelist():
                items_file = zip.open(zipped_file)
                items_file = io.TextIOWrapper(io.BytesIO(items_file.read()))
                csv_reader = csv.reader(items_file)
                data = list(csv_reader)
                sorted(data, key=lambda x: x[0])
                self.assertEqual(['Username', 'Location', 'State'], data[0])
                self.assertCountEqual([
                    ['123.testing@icds-cas.commcare.org', '', ''],
                    ['234.testing@icds-cas.commcare.org', '', ''],
                ], data[1:])

    def tearDown(self):
        user = CommCareUser.get_by_username('123.testing@icds-cas.commcare.org')
        if user:
            user.delete()
        user = CommCareUser.get_by_username('234.testing@icds-cas.commcare.org')
        if user:
            user.delete()
