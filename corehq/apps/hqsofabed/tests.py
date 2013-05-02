from django.test import TestCase
from django.conf import settings
from sofabed.forms.config import get_formdata_class
from corehq.apps.hqsofabed.models import HQFormData

class FormDataTestCase(TestCase):
    
    def testExtend(self):
        settings.FORMDATA_MODEL = "hqsofabed.HQFormData"
        self.assertEqual(HQFormData, get_formdata_class())
        