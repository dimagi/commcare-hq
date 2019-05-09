from __future__ import absolute_import, print_function
from __future__ import unicode_literals

from django.core.management.base import BaseCommand
from django.test import override_settings

from custom.icds_reports.utils.aggregation_helpers.tests.tests import get_agg_helper_outputs


class Command(BaseCommand):
    help = "Update the SQL output files for ICDS Aggregation helpers"

    def handle(self, *args, **options):
        with override_settings(SERVER_ENVIRONMENT='icds'):
            for output in get_agg_helper_outputs():
                output.write()
