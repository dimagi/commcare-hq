from unmagic import use

from corehq.apps.public_webforms.tests.utils import webform_domain
from corehq.apps.public_webforms.utils import public_webforms_enabled
from corehq.privileges import PUBLIC_WEBFORMS
from corehq.util.test_utils import flag_enabled, privilege_enabled


@use('db', webform_domain)
class TestPublicWebformsEnabled:

    @flag_enabled('PUBLIC_WEBFORMS')
    @privilege_enabled(PUBLIC_WEBFORMS)
    def test_enabled_for_an_active_project_with_the_flag_and_privilege(self):
        assert public_webforms_enabled(webform_domain().name)

    @privilege_enabled(PUBLIC_WEBFORMS)
    def test_not_enabled_without_the_flag(self):
        assert not public_webforms_enabled(webform_domain().name)

    @flag_enabled('PUBLIC_WEBFORMS')
    def test_not_enabled_without_the_privilege(self):
        assert not public_webforms_enabled(webform_domain().name)

    @flag_enabled('PUBLIC_WEBFORMS')
    @privilege_enabled(PUBLIC_WEBFORMS)
    def test_not_enabled_for_an_inactive_project(self):
        domain_obj = webform_domain()
        domain_obj.is_active = False
        domain_obj.save()

        assert not public_webforms_enabled(domain_obj.name)
