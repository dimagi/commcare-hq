from datetime import date, datetime
from unittest.mock import MagicMock, patch

from django.core.management import call_command
from django.db.models import BooleanField, DateTimeField, IntegerField
from django.test import SimpleTestCase, TestCase, override_settings

from time_machine import travel

from dimagi.utils.parsing import json_format_datetime

from corehq.apps.accounting.models import (
    DefaultProductPlan,
    SoftwarePlanEdition,
)
from corehq.apps.accounting.tests import generator as accounting_generator
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.es import domain_adapter, form_adapter
from corehq.apps.es.tests.utils import es_test
from corehq.form_processor.tests.utils import create_form_for_test

from ..models import DomainMetrics
from ..tasks import (
    _collect_feature_metrics_for_domain,
    _iter_domain_names_standard_and_higher,
    get_domains_to_update,
)


@es_test(requires=[domain_adapter, form_adapter], setup_class=True)
class TestGetDomainsToUpdate(TestCase):
    def test_domain_metrics_never_updated_is_included(self):
        domain = self.index_domain('never-updated')
        with self.assertRaises(DomainMetrics.DoesNotExist):
            DomainMetrics.objects.get(domain=domain.name)

        domains = get_domains_to_update()
        self.assertEqual(domains, {domain.name})

    @travel('2024-01-10', tick=False)
    def test_domain_metrics_updated_over_one_week_ago_is_included(self):
        domain = self.index_domain('cp-over-one-week')
        self.create_domain_metrics(domain.name, last_modified=datetime(2024, 1, 2, 23, 59))

        domains = get_domains_to_update()
        self.assertEqual(domains, {domain.name})

    @travel('2024-01-10', tick=False)
    def test_domain_metrics_updated_exactly_one_week_ago_is_excluded(self):
        domain = self.index_domain('cp-one-week')
        self.create_domain_metrics(domain.name, last_modified=datetime(2024, 1, 3))

        domains = get_domains_to_update()
        self.assertEqual(domains, set())

    @travel('2024-01-10', tick=False)
    def test_domain_metrics_updated_less_than_one_week_ago_is_excluded(self):
        domain = self.index_domain('cp-less-than-one-week')
        self.create_domain_metrics(domain.name, last_modified=datetime(2024, 1, 4))

        domains = get_domains_to_update()
        self.assertEqual(domains, set())

    @travel('2024-01-10', tick=False)
    def test_form_submission_in_the_last_day_is_included(self):
        domain = self.index_domain('form-from-today')
        self.index_form(domain.name, received_on=datetime(2024, 1, 9, 0, 0))
        self.create_domain_metrics(domain.name, last_modified=datetime(2024, 1, 9))

        domains = get_domains_to_update()
        self.assertEqual(domains, {domain.name})

    @travel('2024-01-10', tick=False)
    def test_form_submission_over_one_day_ago_is_excluded(self):
        domain = self.index_domain('form-from-yesterday')
        self.index_form(domain.name, received_on=datetime(2024, 1, 8, 23, 59))
        self.create_domain_metrics(domain.name, last_modified=datetime(2024, 1, 9))

        domains = get_domains_to_update()
        self.assertEqual(domains, set())

    @travel('2024-01-10', tick=False)
    def test_inactive_domain_is_excluded(self):
        domain = self.index_domain('inactive-domain', active=False)
        self.create_domain_metrics(domain.name)

        domains = get_domains_to_update()
        self.assertEqual(domains, set())

    def index_domain(self, name, active=True, cp_last_updated=None):
        domain = create_domain(name, active)
        self.addCleanup(domain.delete)
        if cp_last_updated:
            domain.cp_last_updated = json_format_datetime(cp_last_updated)
        domain_adapter.index(domain, refresh=True)
        self.addCleanup(domain_adapter.delete, domain._id, refresh=True)
        return domain

    def index_form(self, domain, received_on):
        xform = create_form_for_test(domain, received_on=received_on)
        form_adapter.index(xform, refresh=True)
        self.addCleanup(form_adapter.delete, xform.form_id, refresh=True)
        return xform

    def create_domain_metrics(self, domain, last_modified=None):
        metrics_dict = {}
        for metrics_field in DomainMetrics._meta.get_fields():
            if isinstance(metrics_field, BooleanField):
                metrics_dict[metrics_field.name] = False
            if isinstance(metrics_field, DateTimeField):
                metrics_dict[metrics_field.name] = datetime(2024, 1, 1)
            if isinstance(metrics_field, IntegerField):
                metrics_dict[metrics_field.name] = 0
        domain_metrics = DomainMetrics.objects.create(domain=domain, **metrics_dict)
        self.addCleanup(domain_metrics.delete)
        if last_modified:
            DomainMetrics.objects.filter(domain=domain).update(last_modified=last_modified)


class TestCollectFeatureMetrics(SimpleTestCase):

    TASKS_PATH = 'corehq.apps.data_analytics.tasks'

    @patch(f'{TASKS_PATH}.collect_metrics_for_domain')
    @patch('corehq.apps.domain.models.Domain.get_by_name')
    def test_updates_domain_metrics(self, mock_get_by_name, mock_collect):
        mock_collect.return_value = {'has_multimedia': True}
        domain_obj = MagicMock()
        domain_obj.name = 'test-domain'
        mock_get_by_name.return_value = domain_obj

        with patch(f'{self.TASKS_PATH}.DomainMetrics') as MockMetrics:
            MockMetrics.objects.filter.return_value.first.return_value = MagicMock()
            _collect_feature_metrics_for_domain('test-domain')

        mock_collect.assert_called_once()
        MockMetrics.objects.filter.return_value.update.assert_called_once_with(
            has_multimedia=True,
        )

    @patch(f'{TASKS_PATH}.collect_metrics_for_domain')
    @patch('corehq.apps.domain.models.Domain.get_by_name')
    def test_skips_when_no_updates(self, mock_get_by_name, mock_collect):
        mock_collect.return_value = {}
        domain_obj = MagicMock()
        domain_obj.name = 'test-domain'
        mock_get_by_name.return_value = domain_obj

        with patch(f'{self.TASKS_PATH}.DomainMetrics') as MockMetrics:
            MockMetrics.objects.filter.return_value.first.return_value = MagicMock()
            _collect_feature_metrics_for_domain('test-domain')

        MockMetrics.objects.filter.return_value.update.assert_not_called()

    @patch(f'{TASKS_PATH}.collect_metrics_for_domain')
    @patch('corehq.apps.domain.models.Domain.get_by_name')
    def test_skips_when_no_existing_metrics(self, mock_get_by_name, mock_collect):
        # If no DomainMetrics row exists yet, skip — we cannot create one
        # because daily metric fields are NOT NULL without default values.
        domain_obj = MagicMock()
        domain_obj.name = 'test-domain'
        mock_get_by_name.return_value = domain_obj

        with patch(f'{self.TASKS_PATH}.DomainMetrics') as MockMetrics:
            MockMetrics.objects.filter.return_value.first.return_value = None
            _collect_feature_metrics_for_domain('test-domain')

        mock_collect.assert_not_called()

    @patch('corehq.apps.domain.models.Domain.get_by_name')
    def test_skips_when_domain_not_found(self, mock_get_by_name):
        mock_get_by_name.return_value = None

        # Should not raise
        _collect_feature_metrics_for_domain('nonexistent-domain')


class TestIterDomainNamesStandardAndHigher(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        accounting_generator.bootstrap_test_software_plan_versions()
        cls.account = accounting_generator.billing_account(
            accounting_generator.create_arbitrary_web_user_name(is_dimagi=True),
            accounting_generator.create_arbitrary_web_user_name(),
        )

    def _subscribe(
        self,
        domain,
        edition=SoftwarePlanEdition.STANDARD,
        plan_version=None,
    ):
        if plan_version is None:
            plan_version = DefaultProductPlan.get_default_plan_version(edition=edition)
        accounting_generator.generate_domain_subscription(
            self.account,
            domain,
            date_start=date.today(),
            date_end=None,
            plan_version=plan_version,
            is_active=True,
        )

    def test_includes_standard_domain(self):
        domain = accounting_generator.arbitrary_domain()
        self._subscribe(domain, SoftwarePlanEdition.STANDARD)

        result = list(_iter_domain_names_standard_and_higher())
        assert domain.name in result

    def test_excludes_free_domain(self):
        domain = accounting_generator.arbitrary_domain()
        self._subscribe(domain, SoftwarePlanEdition.FREE)

        result = list(_iter_domain_names_standard_and_higher())
        assert domain.name not in result

    def test_excludes_inactive_subscription(self):
        domain = accounting_generator.arbitrary_domain()
        plan_version = DefaultProductPlan.get_default_plan_version(
            edition=SoftwarePlanEdition.STANDARD
        )
        accounting_generator.generate_domain_subscription(
            self.account,
            domain,
            date_start=date.today(),
            date_end=None,
            plan_version=plan_version,
            is_active=False,
        )

        result = list(_iter_domain_names_standard_and_higher())
        assert domain.name not in result

    def test_excludes_dimagi_only_enterprise(self):
        domain = accounting_generator.arbitrary_domain()
        with override_settings(DEBUG=True):
            call_command('make_domain_enterprise_level', domain.name)

        result = list(_iter_domain_names_standard_and_higher())
        assert domain.name not in result
