from django.core.cache import cache
from django.test import TestCase
from corehq.apps.app_manager.models import Application
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.receiverwrapper.util import get_version_from_build_id
from couchforms.models import XFormInstance
from couchforms.util import spoof_submission


class TestAppId(TestCase):
    form_instances = []

    @classmethod
    def setUpClass(cls):
        cls.domain = 'alskdjfablasdkffsdlkfjabas'
        cls.project = create_domain(name=cls.domain)
        cls.app = Application(domain=cls.domain, version=4)
        cls.app.save()
        cls.app_id = cls.app.get_id
        cls.build = Application(domain=cls.domain, version=3)
        cls.build.copy_of = cls.app_id
        cls.build.save()
        cls.build_id = cls.build.get_id

    @classmethod
    def tearDownClass(cls):
        for form in cls.form_instances:
            form.delete()
        cls.project.delete()

    def test(self):
        cache.clear()
        self._test(self.build_id, self.app_id, self.build_id)
        self._test(self.app_id, self.app_id, None)
        self._test('alskdjflaksdjf', 'alskdjflaksdjf', None)
        self.app.delete_app()
        # does this work just as well for a deleted app?
        cache.clear()
        self._test(self.build_id, self.app_id, self.build_id)
        self.build.delete_app()
        cache.clear()
        form = self._test(self.build_id, self.app_id, self.build_id)
        self._test_app_version(self.domain, form, self.build)
        # (test cache hit)
        self._test_app_version(self.domain, form, self.build)

    def _test(self, id, expected_app_id, expected_build_id):
        # this should be renamed to reflect what it is testing
        r = spoof_submission(
            '/a/{domain}/receiver/{id}/'.format(domain=self.domain, id=id),
            '<data xmlns="http://example.com/"><question1/></data>',
            hqsubmission=False,
        )
        form_id = r['X-CommCareHQ-FormID']
        form = XFormInstance.get(form_id)
        self.assertEqual(form.app_id, expected_app_id)
        self.assertEqual(form.build_id, expected_build_id)
        self.form_instances.append(form)
        return form

    def _test_app_version(self, domain, form, build):
        self.assertEqual(build.version, 3)
        self.assertEqual(get_version_from_build_id(domain, form.build_id),
                         build.version)
