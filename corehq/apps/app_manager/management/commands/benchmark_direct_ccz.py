
import json

from django.core.management import BaseCommand

from dimagi.utils.decorators.profile import profile

from corehq.apps.app_manager.dbaccessors import get_app
from corehq.apps.app_manager.management.commands.benchmark_build_times import (
    Timer,
)
from corehq.apps.app_manager.views.cli import get_direct_ccz


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument(
            'domain_app_id_pairs',
            help='A JSON list where each element has the format [<domain>, <app_id>]',
            type=json.loads,
        )
        parser.add_argument(
            '--profile',
            action='store_true',
            default=False,
            help='Profile in addition to benchmarking',
        )

    def handle(self, domain_app_id_pairs, profile, **options):
        func = _profile_and_benchmark if profile else _code_to_benchmark
        for (domain, app_id) in domain_app_id_pairs:
            print("%s: %s" % (domain, app_id))
            with Timer():
                func(domain, app_id)


def _code_to_benchmark(domain, app_id):
    app = get_app(domain, app_id)
    get_direct_ccz(domain, app, None, None)


@profile('direct_ccz.prof')
def _profile_and_benchmark(domain, app_id):
    _code_to_benchmark(domain, app_id)
