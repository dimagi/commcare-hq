import sys

from django.conf import settings
from django.core.management import color_style
from django.utils.functional import cached_property

from corehq.apps.domain.models import Domain


def abort():
    print("Aborting")
    sys.exit(1)


def confirm_destructive_operation():
    style = color_style()
    print(style.ERROR("\nHEY! This is wicked dangerous, pay attention."))
    print(style.WARNING("\nThis operation irreversibly deletes a lot of stuff."))
    print(f"\nSERVER_ENVIRONMENT = {settings.SERVER_ENVIRONMENT}")

    if settings.IS_SAAS_ENVIRONMENT:
        print("This command isn't meant to be run on a SAAS environment")
        abort()

    confirm("Are you SURE you want to proceed?")


def confirm(msg):
    print(msg)
    if input("(y/N)") != 'y':
        abort()


class DeletedDomains:
    """
    The logic to ensure a domain is deleted is inefficient.
    This object takes advantage of the fact that we typically want this info
    on more than one domain, so it makes sense to cache the results of deleted
    and active domains.
    """

    def __init__(self, deleted_domains=None, active_domains=None):
        self._deleted_domains = deleted_domains
        self._active_domains = active_domains

    def get_deleted_domains(self):
        if not self._deleted_domains:
            self._deleted_domains = Domain.get_deleted_domain_names()
        return self._deleted_domains

    def get_active_domains(self):
        if not self._active_domains:
            self._active_domains = set(Domain.get_all_names())
        return self._active_domains

    def is_domain_deleted(self, domain):
        return domain in self.get_deleted_domains() and domain not in self.get_active_domains()
