from __future__ import absolute_import
from __future__ import unicode_literals
from __future__ import division

from six.moves import input

from django.core.management import BaseCommand
from django.db.models import Q

from corehq.apps.accounting.models import (
    Subscription,
    SoftwarePlanEdition,
)
from corehq.feature_previews import EXPLORE_CASE_DATA_PREVIEW
from corehq.toggles import (
    ECD_MIGRATED_DOMAINS,
    NAMESPACE_DOMAIN,
    ECD_PREVIEW_ENTERPRISE_DOMAINS,
)


class Command(BaseCommand):
    help = 'Enables the Case Search Index for Explore Case Data Report'

    def add_arguments(self, parser):
        parser.add_argument(
            '--domain',
            action='store',
            dest='domain',
            default=None,
            help='A single domain to rollout ECD preview to.',
        )
        parser.add_argument(
            '--deativate-domain',
            action='store',
            dest='deactivate_domain',
            default=None,
            help='A single domain to deactivate ECD preview to'
        )
        parser.add_argument(
            '--deativate',
            action='store_true',
            dest='deactivate',
            default=False,
            help='Deactivate all ineligible domains.'
        )

    def _domains_in_beta(self):
        relevant_subs = Subscription.visible_objects.filter(
            is_active=True,
            is_trial=False,
        ).filter(
            Q(plan_version__plan__edition=SoftwarePlanEdition.ADVANCED) |
            Q(plan_version__plan__edition=SoftwarePlanEdition.PRO)
        ).all()
        domains = set([sub.subscriber.domain for sub in relevant_subs])

        enterprise_domains = set(ECD_PREVIEW_ENTERPRISE_DOMAINS.get_enabled_domains())
        domains = domains.union(enterprise_domains)
        migrated_domains = set(ECD_MIGRATED_DOMAINS.get_enabled_domains())

        return domains.intersection(migrated_domains)

    def _domains_needing_activation(self):
        domains_in_beta = self._domains_in_beta()
        preview_domains = set(EXPLORE_CASE_DATA_PREVIEW.get_enabled_domains())
        return domains_in_beta.difference(preview_domains)

    def _domains_needing_deactivation(self):
        preview_domains = set(EXPLORE_CASE_DATA_PREVIEW.get_enabled_domains())
        return preview_domains.difference(self._domains_in_beta())

    def handle(self, **options):
        domain = options.pop('domain')
        deactivate_domain = options.pop('deactivate_domain')
        deactivate = options.pop('deactivate')

        if deactivate:
            self.update_domains(
                self._domains_needing_deactivation(),
                'deactivation',
                False
            )
            return

        if deactivate_domain:
            EXPLORE_CASE_DATA_PREVIEW.set(deactivate_domain, False,
                                          NAMESPACE_DOMAIN)
            self.stdout.write('\n\nDomain {} deactivated.\n\n'.format(
                deactivate_domain))
            return

        if domain:
            if domain not in ECD_MIGRATED_DOMAINS.get_enabled_domains():
                self.stdout.write('\n\nDomain {} not migrated yet. '
                                  'Activation not possible.\n\n'.format(domain))
                return
            EXPLORE_CASE_DATA_PREVIEW.set(domain, True, NAMESPACE_DOMAIN)
            self.stdout.write('\n\nDomain {} activated.\n\n'.format(domain))
            return

        self.update_domains(
            self._domains_needing_activation(),
            'activation',
            True
        )

    def update_domains(self, domains, action_name, action_state):
        if not domains:
            self.stdout.write('\n\nNo domains need {}.'.format(action_name))
            return

        self.stdout.write('\n\nDomains needing {}\n'.format(action_name))
        self.stdout.write('\n'.join(domains))

        confirm = input('\n\nContinue with {}? [y/n] '.format(action_name))
        if not confirm == 'y':
            self.stdout.write('\nAborting {}\n\n'.format(action_name))
            return
        self.stdout.write('\n')
        for domain in domains:
            self.stdout.write('.')
            EXPLORE_CASE_DATA_PREVIEW.set(domain, action_state, NAMESPACE_DOMAIN)
        self.stdout.write('\n\nDone.\n\n')
