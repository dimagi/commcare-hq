from django.core.cache import cache
from django.test import TestCase
from corehq.apps.app_manager.models import Application
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.receiverwrapper.util import get_version_from_build_id
from couchforms.models import XFormInstance
from couchforms.util import spoof_submission


class TestAppId(TestCase):
    def test(self):
        self.domain = 'alskdjfablasdkffsdlkfjabas'
        project = create_domain(name=self.domain)
        app = Application(domain=self.domain, version=4)
        app.save()
        app_id = app.get_id
        build = Application(domain=self.domain, version=3)
        build.copy_of = app_id
        build.save()
        build_id = build.get_id
        cache.clear()
        try:
            self._test(build_id, app_id, build_id)
            self._test(app_id, app_id, None)
            self._test('alskdjflaksdjf', 'alskdjflaksdjf', None)
            app.delete_app()
            # does this work just as well for a deleted app?
            cache.clear()
            self._test(build_id, app_id, build_id)
            build.delete_app()
            cache.clear()
            form = self._test(build_id, app_id, build_id)
            self._test_app_version(self.domain, form, build)
            # (test cache hit)
            self._test_app_version(self.domain, form, build)
        finally:
            project.delete()

    def _test(self, id, expected_app_id, expected_build_id):
        r = spoof_submission(
            '/a/{domain}/receiver/{id}/'.format(domain=self.domain, id=id),
            '<data xmlns="http://example.com/"><question1/></data>',
            hqsubmission=False,
        )
        form_id = r['X-CommCareHQ-FormID']
        form = XFormInstance.get(form_id)
        self.assertEqual(form.app_id, expected_app_id)
        self.assertEqual(form.build_id, expected_build_id)
        return form

    def _test_app_version(self, domain, form, build):
        self.assertEqual(build.version, 3)
        self.assertEqual(get_version_from_build_id(domain, form.build_id),
                         build.version)
