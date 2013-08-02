import os

from django.core.urlresolvers import reverse
from django.test import TestCase

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.builds.models import CommCareBuild, BuildSpec
from corehq.apps.app_manager.models import Application, DetailColumn, import_app, APP_V1, ApplicationBase

class TestViews(TestCase):
    def setUp(self):
        self.domain = 'app_manager-TestViews-domain'
        create_domain(self.domain)

    def test_download_file_bad_xform_404(self):
        '''
        This tests that the `download_file` view returns
        HTTP code 404 for XML that cannot be generated...
        in some sense it does not exist.
        '''

        app = Application.new_app(self.domain, "TestApp", application_version=APP_V1)
        module = app.new_module("Module0", "en")

        # These builds are checked in to the repo for use in tests
        build1 = {'version': '1.2.dev', 'build_number': 7106}
        build2 = {'version': '2.7.0', 'build_number': 20655}

        def add_build(version, build_number):
            path = os.path.join(os.path.dirname(__file__), "jadjar")
            jad_path = os.path.join(path, 'CommCare_%s_%s.zip' % (version, build_number))
            CommCareBuild.create_from_zip(jad_path, version, build_number)
        add_build(**build1)
        add_build(**build2)
    
        with open(os.path.join(os.path.dirname(__file__), "data", "invalid_form.xml")) as f:
            xform_str = f.read()
        app.new_form(module.id, name="Form0-0", attachment=xform_str, lang="en")
        app.save()

        response = self.client.get(reverse('app_download_file', kwargs=dict(domain=self.domain,
                                                                            app_id=app.get_id,
                                                                            path='modules-0/forms-0.xml')))
        self.assertEqual(response.status_code, 404)
