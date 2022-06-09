from django.core.management.base import BaseCommand

from corehq.apps.export.dbaccessors import get_properly_wrapped_export_instance
from corehq.apps.export.export import get_export_query
from corehq.apps.reports.analytics.esaccessors import media_export_is_too_big


class Command(BaseCommand):
    help = "Gets multimedia files linked to export instance id"

    def add_arguments(self, parser):
        parser.add_argument(
            'export_id',
            help="The id of the export which files are wanted"
        )

    def handle(self, **options):
        try:
            export_id = options.pop('export_id')
            export = get_properly_wrapped_export_instance(export_id)
            filters = export.get_filters()
            query = get_export_query(export, filters)

            if media_export_is_too_big(query):
                print("There are too many files to export at once.")
            else:
                print("Success!")
        except Exception as e:
            print(e)
