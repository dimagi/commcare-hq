from django.test import TestCase
from corehq.apps.app_manager.models import Application
from corehq.apps.domain.models import Domain
from corehq.apps.domain.utils import guess_domain_language
from corehq.util.test_utils import unit_testing_only


@unit_testing_only
def delete_all_domains():
    domains = list(Domain.get_all())
    Domain.bulk_delete(domains)


class UtilsTests(TestCase):
    domain_name = 'test_domain'

    def setUp(self):
        domain = Domain(name=self.domain_name)
        domain.save()
        for i, lang in enumerate(['en', 'fr', 'fr']):
            app = Application.new_app(domain=self.domain_name, name='app{}'.format(i + 1), lang=lang)
            app.save()

    def tearDown(self):
        domain = Domain.get_by_name(self.domain_name)
        for app in domain.applications():
            app.delete()
        domain.delete()

    def test_guess_domain_language(self):
        lang = guess_domain_language(self.domain_name)
        self.assertEqual('fr', lang)
