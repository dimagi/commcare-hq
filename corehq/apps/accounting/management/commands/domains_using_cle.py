from django.core.management import BaseCommand

from corehq import toggles
from corehq.apps.accounting.models import Subscription


class Command(BaseCommand):
    help = "return privilege usage statistics"

    def handle(self, **options):
        pro_domains = set(Subscription.visible_objects.filter(is_active=True).filter(
            plan_version__plan__edition='Pro'
        ).values_list('subscriber__domain', flat=True).distinct())
        advanced_domains = set(Subscription.visible_objects.filter(is_active=True).filter(
            plan_version__plan__edition='Advanced'
        ).values_list('subscriber__domain', flat=True).distinct())
        enterprise_domains = set(Subscription.visible_objects.filter(is_active=True).filter(
            plan_version__plan__edition='Enterprise'
        ).values_list('subscriber__domain', flat=True).distinct())
        domains_with_priv = pro_domains.union(advanced_domains).union(enterprise_domains)
        domains_with_ff = set(toggles.CASE_LIST_EXPLORER.get_enabled_domains())

        domains_always_cle = domains_with_ff.intersection(domains_with_priv)
        domains_only_ff = domains_with_ff.difference(domains_with_priv)
        new_domains = domains_with_priv.difference(domains_with_ff)

        self.stdout.write("\n\n\nPROJECTS UNCHANGED |||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||\n")
        for domain in domains_always_cle:
            edition = get_edition(domain, pro_domains, advanced_domains, enterprise_domains)
            self.stdout.write(f"{domain}\t{edition}")

        self.stdout.write("\n\n\n\nPROJECTS ONLY FF -------------------------------------------------------\n")
        for domain in domains_only_ff:
            edition = Subscription.visible_objects.filter(is_active=True).filter(
                subscriber__domain=domain).first().plan_version.plan.edition
            self.stdout.write(f"{domain}\t{edition}")

        self.stdout.write("\n\n\n\nNEW PROJECTS -------------------------------------------------------\n")
        for domain in new_domains:
            edition = get_edition(domain, pro_domains, advanced_domains, enterprise_domains)
            self.stdout.write(f"{domain}\t{edition}")


def get_edition(domain, pro, advanced, enterprise):
    edition = None
    if domain in pro:
        edition = "pro"
    if domain in advanced:
        edition = "advanced"
    if domain in enterprise:
        edition = "enterprise"
    if edition is None:
        edition = Subscription.visible_objects.filter(is_active=True).filter(
            subscriber__domain=domain
        ).first().plan_version.plan.edition
    return edition
