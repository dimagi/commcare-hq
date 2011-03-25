"""
This file demonstrates two different styles of tests (one doctest and one
unittest). These will both pass when you run "manage.py test".

Replace these with more appropriate tests for your application.
"""

from django.test import TestCase
from corehq.apps.app_manager.models import Application, DetailColumn
from corehq.apps.domain.models import Domain

class AppManagerTest(TestCase):
    xform_xmlns = "http://mrsexypants.com/test_form"
    xform_str = '<instance><test_form xmlns="%s"></test_form></instance>' % xform_xmlns
    def setUp(self):
        Domain.objects.get_or_create(name="test_domain")
        self.app = Application.new_app("test_domain", "TestApp")

        for i in range(3):
            module = self.app.new_module("Module%d" % i, "en")
            for j in range(3):
                self.app.new_form(module.id, name="Form%d-%d" % (i,j), attachment=self.xform_str, lang="en")
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

#    def testCreateJadJar(self):
#        # make sure this doesn't raise an error
#        self.app.create_jad()

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


