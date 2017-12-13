from __future__ import absolute_import
import doctest
from django.test import TestCase, SimpleTestCase
from custom.openclinica.models import StudySettings, OpenClinicaSettings
import custom.openclinica.utils
from custom.openclinica.utils import get_study_metadata_string

DOMAIN = 'test-domain'
TEST_METADATA = '''<?xml version="1.0" encoding="UTF-8"?>
<ODM FileOID="Study-MetaD20160211142051+0300"
     Description="Study Metadata"
     CreationDateTime="2016-02-11T14:20:51+03:00"
     FileType="Snapshot"
     ODMVersion="1.3"
     xmlns="http://www.cdisc.org/ns/odm/v1.3"
     xmlns:OpenClinica="http://www.openclinica.org/ns/odm_ext_v130/v3.1"
     xmlns:OpenClinicaRules="http://www.openclinica.org/ns/rules/v3.1"
     xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
     xsi:schemaLocation="http://www.cdisc.org/ns/odm/v1.3 OpenClinica-ODM1-3-0-OC2-0.xsd" >
</ODM>
'''


class UtilsTests(TestCase):

    def setUp(self):
        oc_settings = OpenClinicaSettings(
            domain=DOMAIN,
            study=StudySettings(
                is_ws_enabled=False,
                metadata=TEST_METADATA
            )
        )
        oc_settings.save()

    def test_get_metadata_from_settings(self):
        metadata = get_study_metadata_string(DOMAIN)
        self.assertEqual(metadata, TEST_METADATA)


class DocTests(SimpleTestCase):

    def test_doctests(self):
        results = doctest.testmod(custom.openclinica.utils)  # Dumps errors to stderr
        self.assertEqual(results.failed, 0)  # results.failed counts both failures and errors
