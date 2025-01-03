from datetime import datetime

from django.db.models import BooleanField, DateTimeField, IntegerField
from django.test import TestCase

from freezegun import freeze_time

from dimagi.utils.parsing import json_format_datetime

from corehq.apps.data_analytics.models import DomainMetrics
from corehq.apps.data_analytics.tasks import get_domains_to_update
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.es import domain_adapter, form_adapter
from corehq.apps.es.tests.utils import es_test
from corehq.form_processor.tests.utils import create_form_for_test


@es_test(requires=[domain_adapter, form_adapter], setup_class=True)
class TestGetDomainsToUpdate(TestCase):
    def test_domain_metrics_never_updated_is_included(self):
        domain = self.index_domain('never-updated')
        with self.assertRaises(DomainMetrics.DoesNotExist):
            DomainMetrics.objects.get(domain=domain.name)

        domains = get_domains_to_update()
        self.assertEqual(domains, {domain.name})

    @freeze_time('2024-01-10')
    def test_domain_metrics_updated_over_one_week_ago_is_included(self):
        domain = self.index_domain('cp-over-one-week')
        self.create_domain_metrics(domain.name, last_modified=datetime(2024, 1, 2, 23, 59))

        domains = get_domains_to_update()
        self.assertEqual(domains, {domain.name})

    @freeze_time('2024-01-10')
    def test_domain_metrics_updated_exactly_one_week_ago_is_excluded(self):
        domain = self.index_domain('cp-one-week')
        self.create_domain_metrics(domain.name, last_modified=datetime(2024, 1, 3))

        domains = get_domains_to_update()
        self.assertEqual(domains, set())

    @freeze_time('2024-01-10')
    def test_domain_metrics_updated_less_than_one_week_ago_is_excluded(self):
        domain = self.index_domain('cp-less-than-one-week')
        self.create_domain_metrics(domain.name, last_modified=datetime(2024, 1, 4))

        domains = get_domains_to_update()
        self.assertEqual(domains, set())

    @freeze_time('2024-01-10')
    def test_form_submission_in_the_last_day_is_included(self):
        domain = self.index_domain('form-from-today')
        self.index_form(domain.name, received_on=datetime(2024, 1, 9, 0, 0))
        self.create_domain_metrics(domain.name, last_modified=datetime(2024, 1, 9))

        domains = get_domains_to_update()
        self.assertEqual(domains, {domain.name})

    @freeze_time('2024-01-10')
    def test_form_submission_over_one_day_ago_is_excluded(self):
        domain = self.index_domain('form-from-yesterday')
        self.index_form(domain.name, received_on=datetime(2024, 1, 8, 23, 59))
        self.create_domain_metrics(domain.name, last_modified=datetime(2024, 1, 9))

        domains = get_domains_to_update()
        self.assertEqual(domains, set())

    @freeze_time('2024-01-10')
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
