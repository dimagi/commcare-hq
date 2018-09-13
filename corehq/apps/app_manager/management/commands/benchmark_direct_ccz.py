from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import json

from django.core.management import BaseCommand

from corehq.apps.app_manager.dbaccessors import get_app
from corehq.apps.app_manager.management.commands.benchmark_build_times import Timer
from corehq.apps.app_manager.views.cli import get_direct_ccz


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument(
            'domain_app_id_pairs',
            help='A JSON list where each element has the format [<domain>, <app_id>]',
            type=json.loads,
        )

    def handle(self, domain_app_id_pairs, **options):
        for (domain, app_id) in domain_app_id_pairs:
            print("%s: %s" % (domain, app_id))
            with Timer():
                app = get_app(domain, app_id)
                get_direct_ccz(domain, app, None, None)
