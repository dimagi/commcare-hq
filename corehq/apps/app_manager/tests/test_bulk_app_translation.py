import os
import codecs

from django.test.client import Client
from django.test import TestCase
from corehq import Domain

from corehq.apps.app_manager.tests.util import add_build
from corehq.apps.app_manager.models import Application, DetailColumn, import_app, APP_V1, ApplicationBase, Module, \
    get_app
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.reports.formdetails.readable import FormQuestion
from corehq.apps.users.models import WebUser


class BulkAppTranslationTest(TestCase):
    with codecs.open(os.path.join(os.path.dirname(__file__), "data", "bulk_translate_test_form.xml"), encoding='utf-8') as f:
        xform_str = f.read()

    def setUp(self):

        self.client = Client()

        self.domain = Domain(name="test-domain", is_active=True)
        self.domain.save()

        self.username = 'bulk-jhghgjdfdfg-user'
        self.password = 'my-password'
        self.user = WebUser.create(self.domain.name, self.username, self.password)
        self.user.set_role(self.domain.name, 'admin')
        self.user.save()

        self.app = Application.new_app(self.domain.name, "TestApp", application_version=APP_V1)
        self.app.build_langs.append("fra")
        self.app.langs.append("fra")

        for i in range(2):
            module = self.app.add_module(Module.new_module("Module%d" % i, "en"))
            for j in range(2):
                self.app.new_form(module.id, name="Form%s-%s" % (i,j), attachment=self.xform_str, lang="en")
            module = self.app.get_module(i)
            short_detail = module.case_details.short
            long_detail = module.case_details.long

            if i == 0 and j == 0:
                e = [{
                    'key': 'mykey1',
                    'value': {
                        "en": 'myval1',
                    }
                },
                {
                    'key': 'mykey2',
                    'value': {
                        "en": 'myval2',
                }}]
                d1 = DetailColumn(header={"en": "test1"}, model="case", field="test1", format="plain")
                d2 = DetailColumn(header={"en": "test2"}, modul="case", field="test2", format="enum", enum=e)
                short_detail.append(d1)
                short_detail.append(d2)
                long_detail.append(d1)
                long_detail.append(d2)

        self.build = {'version': "2.7.0", 'build_number': 20655}
        add_build(**self.build)
        self.app.save()

    def test_download(self):
        # Download the sheet
        # Somehow compare the sheets
        pass

    def test_upload(self):
        with codecs.open(os.path.join(os.path.dirname(__file__), "data", "bulk_app_translation.xlsx")) as f:
            # TODO: Reverse the url instead of hard coding
            self.client.login(username=self.username, password=self.password)
            response = self.client.post('/a/%s/apps/view/%s/languages/bulk_app_translations/upload/' % (self.app.domain, self.app.id),
                   {'bulk_upload_file': f},
                   follow=True
            )
            import ipdb; ipdb.set_trace()
            print response
        app = get_app(self.app.domain, self.app.id)
        form = app.get_module(0).get_form(0)

        labels = {}
        for lang in app.langs:
            for question in form.get_questions([lang], include_triggers=True, include_groups=True):
                labels[(question['value'], lang)] = question['label']

        # Test new translation (of question and prop and form and module)
        self.assertEqual(labels[("/data/question1", "en")], "in english")
        self.assertEqual(labels[("/data/question1", "fr")], "in french")