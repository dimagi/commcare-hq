from django.core.management import BaseCommand

from corehq import toggles
from corehq.apps.accounting.models import Subscription


class Command(BaseCommand):
    help = "return privilege usage statistics"

    def handle(self, **options):
        domains_with_priv = set(Subscription.visible_objects.exclude(
            plan_version__plan__edition__in='Paused,Community,Standard'
        ).values_list('subscriber__domain', flat=True).distinct())
        domains_with_ff = set(toggles.CASE_LIST_EXPLORER.get_enabled_domains())

        domains_always_cle = domains_with_ff.intersection(domains_with_priv)
        domains_only_ff = domains_with_ff.difference(domains_with_priv)
        new_domains = domains_with_priv.difference(domains_with_ff)

        self.stdout.write("\n\n\nPROJECTS UNCHANGED\n")
        self.stdout.write("\n".join(domains_always_cle))

        self.stdout.write("\n\n\n\nPROJECTS ONLY FF\n")
        self.stdout.write("\n".join(domains_only_ff))

        self.stdout.write("\n\n\n\nNEW PROJECTS\n")
        self.stdout.write("\n".join(new_domains))
        self.stdout.write("\n\n")
