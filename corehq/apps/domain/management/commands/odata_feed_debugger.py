from django.core.management.base import BaseCommand
from corehq.apps.export.models import FormExportDataSchema, FormExportInstance
from corehq.apps.export.views.utils import clean_odata_columns


class Command(BaseCommand):
    help = "Tool for debugging odata feed live on prod"

    def add_arguments(self, parser):
        parser.add_argument(
            'domain',
        )
        parser.add_argument(
            'app_id',
        )
        parser.add_argument(
            'export_id',
        )

    def handle(self, domain, app_id, export_id, **options):
        # def new_export_instance()
        export_instance = FormExportInstance.get(export_id)
        # added in ODataFeedMixin
        export_instance._id = None
        export_instance._rev = None

        # from get BaseEditNewCustomExportView
        schema = FormExportDataSchema.generate_schema_from_builds(
            domain,
            app_id,
            export_instance.identifier,
            only_process_current_builds=True,
        )

        # def get_export_instance in BaseEditNewCustomExportView
        new_instance = FormExportInstance.generate_instance_from_schema(
            schema, export_instance
        )
        # added in ODataFeedMixin
        # clean_odata_columns(new_instance)
        new_instance.is_odata_config = True
        new_instance.transform_dates = False
        new_instance.name = ("Copy of {}").format(new_instance.name)

        for col in new_instance.tables[0].selected_columns:
            if col.is_deleted:
                print(col)
