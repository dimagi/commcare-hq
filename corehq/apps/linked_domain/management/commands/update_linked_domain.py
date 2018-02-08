from __future__ import absolute_import, print_function

from django.core.management import BaseCommand, CommandError

from corehq.apps.linked_domain.dbaccessors import get_domain_master_link
from corehq.apps.linked_domain.updates import (
    update_toggles_previews,
    update_custom_data_models,
    update_user_roles
)


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument('linked_domain')

    def handle(self, linked_domain, **options):
        link = get_domain_master_link(linked_domain)
        if not link:
            raise CommandError("Domain is not linked")

        update_toggles_previews(link)
        update_custom_data_models(link)
        update_user_roles(link)
