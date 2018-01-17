from __future__ import absolute_import
import json
import csv
from django.core.management.base import BaseCommand
from corehq.apps.userreports.models import DataSourceConfiguration


class Command(BaseCommand):
    help = "Find all datasources that use ucr_ext"

    def add_arguments(self, parser):
        parser.add_argument(
            "log_path",
            help="Path to write the log to"
        )

    def handle(self, log_path, **options):
        headers = [
            'domain',
            'datasource_id',
        ]

        with open(log_path, "w") as log_file:
            writer = csv.writer(log_file)
            writer.writerow(headers)

            for config in DataSourceConfiguration.all():
                try:
                    doc_json = json.dumps(config.to_json())
                except:
                    writer.writerow([
                        config.domain,
                        "bad-" + config._id
                    ])

                if '"ext_' in doc_json:
                    writer.writerow([
                        config.domain,
                        config._id
                    ])
