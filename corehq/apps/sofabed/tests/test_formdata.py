from datetime import date, datetime
import os
import pytz
import uuid
from django.test import TestCase
from corehq.apps.hqadmin.dbaccessors import get_all_forms_in_all_domains
from corehq.apps.receiverwrapper.util import submit_form_locally
from couchforms.models import XFormInstance
from corehq.apps.sofabed.dbaccessors import get_form_counts_by_user_xmlns
from corehq.apps.sofabed.models import FormData


class FormDataTestCase(TestCase):

    def setUp(self):

        for item in get_all_forms_in_all_domains():
            item.delete()

        for item in FormData.objects.all():
            item.delete()

        file_path = os.path.join(os.path.dirname(__file__), "data", "meta.xml")
        with open(file_path, "rb") as f:
            xml_data = f.read()

        submit_form_locally(xml_data, 'sofabed', app_id='12345', received_on=datetime.utcnow())

        self.instance = XFormInstance.get('THIS_IS_THE_INSTANCEID')

    def testFromInstance(self):
        formdata = FormData.from_instance(self.instance)
        self.assertEqual(date(2010, 07, 22), formdata.time_start.date())
        self.assertEqual(date(2010, 07, 23), formdata.time_end.date())
        self.assertEqual("THIS_IS_THE_INSTANCEID", formdata.instance_id)
        self.assertEqual("THIS_IS_THE_DEVICEID", formdata.device_id)
        self.assertEqual("THIS_IS_THE_USERID", formdata.user_id)

    def testMatches(self):
        formdata = FormData.from_instance(self.instance)
        self.assertTrue(formdata.matches_exact(self.instance))

        formdata.device_id = "UPDATED_DEVICEID"
        self.assertFalse(formdata.matches_exact(self.instance))

    def testUpdate(self):
        formdata = FormData.from_instance(self.instance)
        self.instance["form"]["meta"]["deviceID"] = "UPDATED_DEVICEID"
        formdata.update(self.instance)
        self.assertEqual("UPDATED_DEVICEID", formdata.device_id)
        self.assertTrue(formdata.matches_exact(self.instance))

    def testCreateOrUpdate(self):
        self.assertEqual(0, FormData.objects.count())

        FormData.create_or_update_from_instance(self.instance)
        self.assertEqual(1, FormData.objects.count())
        self.assertTrue(FormData.objects.all()[0].matches_exact(self.instance))

        FormData.create_or_update_from_instance(self.instance)
        self.assertEqual(1, FormData.objects.count())
        self.assertTrue(FormData.objects.all()[0].matches_exact(self.instance))

        self.instance["form"]["meta"]["deviceID"] = "UPDATED_DEVICEID"
        FormData.create_or_update_from_instance(self.instance)
        self.assertEqual(1, FormData.objects.count())
        self.assertTrue(FormData.objects.all()[0].matches_exact(self.instance))

        self.instance["form"]["meta"]["instanceID"] = "UPDATED_INSTANCEID"
        self.instance._id = "UPDATED_INSTANCEID"
        FormData.create_or_update_from_instance(self.instance)
        self.assertEqual(2, FormData.objects.count())
        self.assertTrue(FormData.objects.get(instance_id="UPDATED_INSTANCEID").matches_exact(self.instance))


def utc_date(y, m, d):
    return datetime(y, m, d, tzinfo=pytz.UTC)


class FormDataQueryTest(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.form_data = []
        for received_on, time_end, xmlns, user_id in [
            (utc_date(2015, 2, 5), utc_date(2015, 1, 24), 'form1', 'user1'),
            (utc_date(2015, 2, 8), utc_date(2015, 2, 7), 'form1', 'user1'),
            (utc_date(2015, 2, 8), utc_date(2015, 2, 7), 'form2', 'user1'),
            (utc_date(2015, 2, 8), utc_date(2015, 2, 7), 'form1', 'user2'),
            (utc_date(2015, 2, 28), utc_date(2015, 2, 1), 'form1', 'user2'),
        ]:
            cls.form_data.append(FormData.objects.create(
                domain='test-domain',
                received_on=received_on,
                time_end=time_end,
                xmlns=xmlns,
                user_id=user_id,
                app_id='app_id',
                time_start=time_end,
                instance_id=uuid.uuid4().hex,
                duration=3,
            ))

    @classmethod
    def tearDownClass(cls):
        for form_datum in cls.form_data:
            form_datum.delete()

    def test_form_counts_by_submission_time(self):
        start, end = utc_date(2015, 2, 1), utc_date(2015, 3, 1)
        counts = get_form_counts_by_user_xmlns('test-domain', start, end)
        self.assertEqual(counts[('user1', 'form1', 'app_id')], 2)
        self.assertEqual(counts[('user1', 'form2', 'app_id')], 1)
        self.assertEqual(counts[('user2', 'form1', 'app_id')], 2)
        self.assertEqual(counts[('user2', 'form2', 'app_id')], 0)

    def test_form_counts_by_completion_time(self):
        start, end = utc_date(2015, 2, 1), utc_date(2015, 3, 1)
        counts = get_form_counts_by_user_xmlns('test-domain', start, end,
                                               by_submission_time=False)
        self.assertEqual(counts[('user1', 'form1', 'app_id')], 1)
        self.assertEqual(counts[('user1', 'form2', 'app_id')], 1)
        self.assertEqual(counts[('user2', 'form1', 'app_id')], 2)
        self.assertEqual(counts[('user2', 'form2', 'app_id')], 0)

    def test_specific_users(self):
        start, end = utc_date(2015, 2, 1), utc_date(2015, 3, 1)
        counts = get_form_counts_by_user_xmlns('test-domain', start, end,
                                               user_ids=['user1'])
        self.assertEqual(counts[('user1', 'form1', 'app_id')], 2)
        self.assertEqual(counts[('user2', 'form1', 'app_id')], 0)

    def test_specific_xmlnss(self):
        start, end = utc_date(2015, 2, 1), utc_date(2015, 3, 1)
        counts = get_form_counts_by_user_xmlns('test-domain', start, end,
                                               xmlnss=['form1'])
        self.assertEqual(counts[('user1', 'form1', 'app_id')], 2)
        self.assertEqual(counts[('user1', 'form2', 'app_id')], 0)
