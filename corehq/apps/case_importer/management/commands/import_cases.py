import json
from datetime import datetime

from django.core.management import BaseCommand

from dimagi.utils.web import json_handler

from corehq.apps.case_importer.do_import import do_import
from corehq.apps.case_importer.util import ImporterConfig, get_spreadsheet


class Command(BaseCommand):
    """
    Import cases locally - useful for large imports or if you're trying to iterate on
    an import in a dev environment.

    The easiest way to generate the config_file argument for this command is to add the following
    lines to case_importer.views.excel_commit and run the import once from the web UI:

      config = importer_util.ImporterConfig.from_request(request)
      # add these two lines after the above one
      import json
      print(json.dumps(config.to_dict(), indent=2))
    """
    help = "Import cases from excel manually."

    def add_arguments(self, parser):
        parser.add_argument('export_file')
        parser.add_argument('config_file')
        parser.add_argument('domain')

    def handle(self, export_file, config_file, domain, **options):
        start = datetime.utcnow()

        with open(config_file, 'r', encoding='utf-8') as f:
            config = ImporterConfig.from_json(f.read())

        with get_spreadsheet(export_file) as spreadsheet:
            print(json.dumps(do_import(spreadsheet, config, domain),
                             default=json_handler))
            print('finished in %s seconds' % (datetime.utcnow() - start).seconds)
