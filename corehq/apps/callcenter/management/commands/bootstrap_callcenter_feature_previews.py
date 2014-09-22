from __future__ import print_function
from optparse import make_option
from couchdbkit.exceptions import ResourceNotFound
from django.core.management.base import BaseCommand
from corehq.apps.callcenter.utils import get_call_center_domains
from corehq.feature_previews import CALLCENTER
from corehq.toggles import NAMESPACE_DOMAIN
from toggle.models import Toggle
from toggle.shortcuts import namespaced_item, update_toggle_cache


class Command(BaseCommand):
    help = 'Enable call center feature preview for all domains that have call center enabled'

    option_list = BaseCommand.option_list + (
        make_option('--dry-run', action='store_true',  default=False,
                    help="Don't actually do anything"),
    )

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)

        if dry_run:
            print("\n-------- DRY RUN --------\n")

        slug = CALLCENTER.slug
        try:
            toggle = Toggle.get(slug)
        except ResourceNotFound:
            toggle = Toggle(slug=slug)
        print("Current domains in toggle: {}".format(toggle.enabled_users))

        domains = get_call_center_domains()
        print("Active call center domains: {}".format(domains))

        items = [namespaced_item(domain, NAMESPACE_DOMAIN) for domain in domains]
        missing = set(items) - set(toggle.enabled_users)
        print("Domains missing from toggle: {}".format(missing))

        toggle.enabled_users = items

        if not dry_run:
            toggle.save()

            for item in items:
                update_toggle_cache(slug, item, True)

