import json
import os

from django.test import TestCase
from corehq.apps.app_manager.models import Application, DetailColumn, import_app, APP_V1, ApplicationBase
from corehq.apps.builds.models import CommCareBuild, BuildSpec
from corehq.apps.domain.shortcuts import create_domain

class AppManagerTest(TestCase):
    with open(os.path.join(os.path.dirname(__file__), "data", "itext_form.xml")) as f:
        xform_str = f.read()

    def setUp(self):
        self.domain = 'test-domain'
        create_domain(self.domain)
        self.app = Application.new_app(self.domain, "TestApp", application_version=APP_V1)

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

        self.build1 = {'version': '1.2.dev', 'build_number': 7106}
        self.build2 = {'version': '2.7.0', 'build_number': 20655}

        def add_build(version, build_number):
            path = os.path.join(os.path.dirname(__file__), "jadjar")
            jad_path = os.path.join(path, 'CommCare_%s_%s.zip' % (version, build_number))
            CommCareBuild.create_from_zip(jad_path, version, build_number)
        add_build(**self.build1)
        add_build(**self.build2)



    def tearDown(self):
        self.app.delete()
        #for xform in XForm.view('app_manager/xforms', key=self.xform_xmlns, reduce=False).all():
        #    xform.delete()

    def testSetUp(self):
        self.assertEqual(len(self.app.modules), 3)
        for module in self.app.get_modules():
            self.assertEqual(len(module.forms), 3)

    def testCreateJadJar(self):
        # make sure this doesn't raise an error
        self.app.build_spec = BuildSpec(**self.build1)
        self.app.create_jadjar()

    def testDeleteForm(self):
        self.app.delete_form(0,0)
        self.assertEqual(len(self.app.modules), 3)
        for module, i in zip(self.app.get_modules(), [2,3,3]):
            self.assertEqual(len(module.forms), i)

    def testDeleteModule(self):
        self.app.delete_module(0)
        self.assertEqual(len(self.app.modules), 2)

    def testSwapDetailColumns(self):
        module = self.app.get_module(0)
        detail = module.get_detail("ref_short")
        self.assertEqual(len(detail.columns), 2)
        self.assertEqual(detail.columns[0].name['en'], 'test')
        self.assertEqual(detail.columns[1].name['en'], 'age')
        self.app.rearrange_detail_columns(module.id, "ref_short", 0, 1)
        self.assertEqual(detail.columns[0].name['en'], 'age')
        self.assertEqual(detail.columns[1].name['en'], 'test')

    def testSwapModules(self):
        m0 = self.app.modules[0].name['en']
        m1 = self.app.modules[1].name['en']
        self.app.rearrange_modules(0,1)
        self.assertEqual(self.app.modules[0].name['en'], m1)
        self.assertEqual(self.app.modules[1].name['en'], m0)

    def testImportApp(self):
        self.failUnless(self.app._attachments)
        new_app = import_app(self.app.id, self.domain)
        self.assertEqual(set(new_app._attachments.keys()).intersection(self.app._attachments.keys()), set())
        new_forms = list(new_app.get_forms())
        old_forms = list(self.app.get_forms())
        for new_form, old_form in zip(new_forms, old_forms):
            self.assertEqual(new_form.source, old_form.source)

    def testAppsBrief(self):
        """Test that ApplicationBase can wrap the
        truncated version returned by applications_brief
        """
        self.app.save()
        apps = ApplicationBase.get_db().view('app_manager/applications_brief',
            startkey=[self.domain],
            limit=1,
        ).all()
        self.assertEqual(len(apps), 1)

    def testBuildApp(self):
        # this app fixture uses both the (new) '_attachment'
        # and the (old) 'contents' conventions, to test that both work
        with open(os.path.join(os.path.dirname(__file__), 'data', 'yesno.json')) as f:
            source = json.load(f)

        # do it from a NOT-SAVED app;
        # regression test against case where contents gets lazy-put w/o saving
        app = Application.wrap(source)
        self.assertEqual(app['_id'], None)  # i.e. hasn't been saved
        copy = app.make_build()
        copy.save()

    def testBuildImportedApp(self):
        with open(os.path.join(os.path.dirname(__file__), 'data', 'yesno.json')) as f:
            source = json.load(f)

        app = import_app(source, self.domain)
        copy = app.make_build()
        copy.save()