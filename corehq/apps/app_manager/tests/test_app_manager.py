"""
This file demonstrates two different styles of tests (one doctest and one
unittest). These will both pass when you run "manage.py test".

Replace these with more appropriate tests for your application.
"""
import os

from django.test import TestCase
from corehq.apps.app_manager.models import Application, DetailColumn, import_app, APP_V1
from corehq.apps.builds.models import CommCareBuild, BuildSpec
from corehq.apps.domain.shortcuts import create_domain

class AppManagerTest(TestCase):
    with open(os.path.join(os.path.dirname(__file__), "data", "itext_form.xml")) as f:
        xform_str = f.read()

    def setUp(self):
        self.domain = 'test-domain'
        create_domain(self.domain)
        self.app = Application.new_app("test_domain", "TestApp", application_version=APP_V1)

        for i in range(3):
            module = self.app.new_module("Module%d" % i, "en")
            for j in range(3):
                self.app.new_form(module.id, name="Form%s-%s" % (i,j), attachment=self.xform_str, lang="en")
            module = self.app.get_module(i)
            detail = module.get_detail("ref_short")
            detail.append_column(
                DetailColumn(name={"en": "test"}, model="case", field="test", format="plain", enum={})
            )
            detail.append_column(
                DetailColumn(name={"en": "age"}, model="case", field="age", format="years-ago", enum={})
            )
        self.app.save()

    def tearDown(self):
        self.app.delete()
        #for xform in XForm.view('app_manager/xforms', key=self.xform_xmlns, reduce=False).all():
        #    xform.delete()

    def testSetUp(self):
        self.failUnlessEqual(len(self.app.modules), 3)
        for module in self.app.get_modules():
            self.failUnlessEqual(len(module.forms), 3)

    def testCreateJadJar(self):
        version = "1.2.dev"
        build_number = 7106
        def make_sure_there_is_a_build():
            path = os.path.join(os.path.dirname(__file__), "jadjar")
            jad_path = os.path.join(path, 'CommCare_%s_%s.zip' % (version, build_number))
            CommCareBuild.create_from_zip(jad_path, version, build_number)
        make_sure_there_is_a_build()
        # make sure this doesn't raise an error
        self.app.build_spec = BuildSpec(version=version, build_number=build_number)
        self.app.create_jadjar()

    def testDeleteForm(self):
        self.app.delete_form(0,0)
        self.failUnlessEqual(len(self.app.modules), 3)
        for module, i in zip(self.app.get_modules(), [2,3,3]):
            self.failUnlessEqual(len(module.forms), i)

    def testDeleteModule(self):
        self.app.delete_module(0)
        self.failUnlessEqual(len(self.app.modules), 2)

    def testSwapDetailColumns(self):
        module = self.app.get_module(0)
        detail = module.get_detail("ref_short")
        self.failUnlessEqual(len(detail.columns), 2)
        self.failUnlessEqual(detail.columns[0].name['en'], 'test')
        self.failUnlessEqual(detail.columns[1].name['en'], 'age')
        self.app.rearrange_detail_columns(module.id, "ref_short", 0, 1)
        self.failUnlessEqual(detail.columns[0].name['en'], 'age')
        self.failUnlessEqual(detail.columns[1].name['en'], 'test')

    def testSwapModules(self):
        m0 = self.app.modules[0].name['en']
        m1 = self.app.modules[1].name['en']
        self.app.rearrange_modules(0,1)
        self.failUnlessEqual(self.app.modules[0].name['en'], m1)
        self.failUnlessEqual(self.app.modules[1].name['en'], m0)


    def testImportApp(self):
        self.failUnless(self.app._attachments)
        new_app = import_app(self.app.id, self.domain)
        self.failUnlessEqual(set(new_app._attachments.keys()).intersection(self.app._attachments.keys()), set())
