from django.test import TestCase

from corehq.apps.app_manager.models import Application, Module
from corehq.apps.data_analytics.metric_registry import DomainContext
from corehq.apps.domain.models import Domain
from corehq.apps.domain.shortcuts import create_domain


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
        cls.addClassCleanup(app.delete)
        cls.addClassCleanup(cls.project.delete)

    def test_domain_context_apps_have_modules(self):
        domain_obj = Domain.get_by_name(self.domain)
        ctx = DomainContext(domain_obj)
        [app] = ctx.apps
        modules = app.get_modules()
        assert len(modules) == 1
        assert modules[0].case_type == 'patient'
