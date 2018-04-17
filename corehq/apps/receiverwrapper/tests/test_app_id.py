from __future__ import absolute_import
from __future__ import unicode_literals
from django.core.cache import cache
from django.test import TestCase
from corehq.apps.app_manager.models import Application
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.receiverwrapper.util import get_version_from_build_id, get_submit_url
from corehq.form_processor.interfaces.dbaccessors import FormAccessors
from corehq.form_processor.tests.utils import use_sql_backend
from couchforms.util import spoof_submission


class TestAppId(TestCase):

    @classmethod
    def setUpClass(cls):
        super(TestAppId, cls).setUpClass()
        cls.domain = 'alskdjfablasdkffsdlkfjabas'
        cls.project = create_domain(name=cls.domain)

        cls.app = Application(domain=cls.domain, version=4)
        cls.app.save()
        cls.app_id = cls.app.get_id

        cls.build = Application(domain=cls.domain, version=3)
        cls.build.copy_of = cls.app_id
        cls.build.save()
        cls.build_id = cls.build.get_id

        cache.clear()

    @classmethod
    def tearDownClass(cls):
        cls.project.delete()
        super(TestAppId, cls).tearDownClass()

    def test(self):
        self._test(self.build_id, self.app_id, self.build_id)
        self._test(self.app_id, self.app_id, None)
        self._test('alskdjflaksdjf', 'alskdjflaksdjf', None)

        # does this work just as well for a deleted app?
        self.app.delete_app()
        cache.clear()
        self._test(self.build_id, self.app_id, self.build_id)

        # and deleted builds
        self.build.delete_app()
        cache.clear()
        form = self._test(self.build_id, self.app_id, self.build_id)

        self._test_app_version(self.domain, form, self.build)
        # (test cache hit)
        self._test_app_version(self.domain, form, self.build)

    def _test(self, submit_app_id, expected_app_id, expected_build_id):
        form_id = spoof_submission(
            get_submit_url(self.domain, submit_app_id),
            '<data xmlns="http://example.com/"><question1/></data>'
        )
        form = FormAccessors(self.domain).get_form(form_id)
        self.assertEqual(form.app_id, expected_app_id)
        self.assertEqual(form.build_id, expected_build_id)
        return form

    def _test_app_version(self, domain, form, build):
        self.assertEqual(build.version, 3)
        self.assertEqual(get_version_from_build_id(domain, form.build_id),
                         build.version)


@use_sql_backend
class TestAppIdSQL(TestAppId):
    pass
