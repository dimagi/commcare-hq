import os

from django.test import TestCase

from buildmanager.tests.util import setup_build_objects 
from buildmanager.models import Project, ProjectBuild, BuildDownload, BuildForm

class BuildTestCase(TestCase):

    def setUp(self):
        user, domain, project, build = setup_build_objects(jar_file_name="Test.jar")
        self.domain = domain
        self.user = user
        self.project = project
        self.build = build

    def testSaveXForms(self):
        # the saving of the build should have auto-created these
        self.assertEqual(2, len(BuildForm.objects.all()))
        all_forms = BuildForm.objects.all()
        self.assertEqual(2, len(all_forms))
        for form in all_forms:
            self.assertEqual(self.build, form.build)
            self.assertTrue(form.get_file_name() in ["brac_chw.xml", "weekly_update.xml"])
        self.assertEqual(2, len(self.build.xforms.all()))
        
        # resave and make sure they don't get replicated
        self.build.description = "some new description"
        self.build.save()
        self.assertEqual(2, len(BuildForm.objects.all()))
        self.assertEqual(2, len(self.build.xforms.all()))
        
        
