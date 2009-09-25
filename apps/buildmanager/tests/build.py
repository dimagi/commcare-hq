import os

from django.test import TestCase

from buildmanager.tests.util import setup_build_objects 
from buildmanager.models import Project, ProjectBuild, BuildDownload, BuildForm

class BuildTestCase(TestCase):

    def setUp(self):
        domain, user, project, build = setup_build_objects(jar_file_name="Test.jar")
        self.domain = domain
        self.user = user
        self.project = project
        self.build = build

    def testSaveXForms(self):
        self.assertEqual(0, len(BuildForm.objects.all()))
        self.build.extract_and_link_xforms()
        all_forms = BuildForm.objects.all()
        self.assertEqual(2, len(all_forms))
        for form in all_forms:
            self.assertEqual(self.build, form.build)
            self.assertTrue(form.get_file_name() in ["brac_chw.xml", "weekly_update.xml"])
        self.assertEqual(2, len(self.build.xforms.all()))
        
                