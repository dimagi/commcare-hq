from __future__ import absolute_import
from __future__ import unicode_literals
from django.core.management.base import BaseCommand

from toggle.shortcuts import set_toggle

from corehq.form_processor.utils import use_new_exports
from corehq.apps.domain.models import Domain
from corehq.apps.hqwebapp.templatetags.hq_shared_tags import toggle_js_domain_cachebuster
from corehq import toggles


class Command(BaseCommand):
    help = "Migrates old exports to new ones"

    def handle(self, **options):
        for doc in Domain.get_all(include_docs=False):
            domain = doc['key']
            if not use_new_exports(domain):
                set_toggle(
                    toggles.OLD_EXPORTS.slug,
                    domain,
                    True,
                    namespace=toggles.NAMESPACE_DOMAIN
                )
                toggle_js_domain_cachebuster.clear(domain)
