from __future__ import print_function
from __future__ import absolute_import
from __future__ import unicode_literals
import json
from datetime import datetime
from django.core.management import BaseCommand, CommandError
from dimagi.utils.web import json_handler
from corehq.apps.case_importer.do_import import do_import
from corehq.apps.case_importer.util import ImporterConfig, get_spreadsheet
from corehq.apps.users.models import WebUser
from io import open


class Command(BaseCommand):
    help = "import cases from excel manually."

    def add_arguments(self, parser):
        parser.add_argument('export_file')
        parser.add_argument('config_file')
        parser.add_argument('domain')
        parser.add_argument('user_id')

    def handle(self, export_file, config_file, domain, user_id, **options):
        start = datetime.utcnow()

        if '@' in user_id:
            user = WebUser.get_by_username(user_id)
        else:
            user = WebUser.get(user_id)
        if not user.is_member_of(domain):
            raise CommandError("%s can't access %s" % (user, domain))

        with open(config_file, 'r', encoding='utf-8') as f:
            config = ImporterConfig.from_json(f.read())

        config.couch_user_id = user._id
        with get_spreadsheet(export_file) as spreadsheet:
            print(json.dumps(do_import(spreadsheet, config, domain),
                             default=json_handler))
            print('finished in %s seconds' % (datetime.utcnow() - start).seconds)
