from django.test import TestCase

from corehq.apps.app_manager.models import Application, Module
from corehq.apps.data_analytics.metric_registry import DomainContext
from corehq.apps.domain.models import Domain
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.es.apps import app_adapter
from corehq.apps.es.tests.utils import es_test


@es_test(requires=[app_adapter], setup_class=True)
class TestDomainContextLoadsFullApps(TestCase):
    domain = 'data-analytics-apps-test'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.project = create_domain(cls.domain)
        app = Application.wrap(
            Application(
                domain=cls.domain,
                name='x',
                version=1,
                modules=[Module(case_type='patient')],
            ).to_json()
        )
        app.save()
        cls.addClassCleanup(app.delete_app)
        cls.addClassCleanup(cls.project.delete)

    def test_domain_context_apps_have_modules(self):
        domain_obj = Domain.get_by_name(self.domain)
        ctx = DomainContext(domain_obj)
        [app] = ctx.apps
        [module] = list(app.get_modules())
        assert module.case_type == 'patient'
