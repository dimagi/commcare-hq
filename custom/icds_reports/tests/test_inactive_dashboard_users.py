import csv
import io
import shutil
import zipfile
from tempfile import NamedTemporaryFile

from django.test.testcases import TestCase

from corehq.apps.users.models import CommCareUser
from custom.icds_reports.models.helper import IcdsFile
from custom.icds_reports.tasks import collect_inactive_dashboard_users


class TestInactiveMobileUsers(TestCase):

    def test_get_inactive_users(self):
        IcdsFile.objects.filter(data_type='inactive_dashboard_users').all().delete()
        collect_inactive_dashboard_users()
        sync = IcdsFile.objects.filter(data_type='inactive_dashboard_users').order_by('-file_added').first()
        with sync.get_file_from_blobdb() as fileobj, NamedTemporaryFile() as out:
            shutil.copyfileobj(fileobj, out)
            zip = zipfile.ZipFile(out, 'r')
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
        with sync.get_file_from_blobdb() as fileobj, NamedTemporaryFile() as out:
            shutil.copyfileobj(fileobj, out)
            zip = zipfile.ZipFile(out, 'r')
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
