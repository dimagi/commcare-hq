from django.test import TestCase
from couchforms.models import XFormInstance
from couchforms.util import SubmissionPost
import os
from corehq.apps.sofabed.models import FormData
from datetime import date, datetime


class FormDataTestCase(TestCase):

    def setUp(self):

        for item in XFormInstance.view("hqadmin/forms_over_time", include_docs=True, reduce=False).all():
            item.delete()

        for item in FormData.objects.all():
            item.delete()

        file_path = os.path.join(os.path.dirname(__file__), "data", "meta.xml")
        with open(file_path, "rb") as f:
            xml_data = f.read()

        SubmissionPost(
            instance=xml_data,
            domain='sofabed',
            app_id='12345',
            received_on=datetime.now()
        ).get_response()

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
