import json

from django.core.management.base import BaseCommand
from corehq.apps.users.models import CommCareUser, CommCareCase
from dimagi.utils.couch.database import get_db

from custom.opm.reports.tests import test_data_location

class Command(BaseCommand):
    help = "Pull data from the database and write\
        to a json file (currently only works for opm"

    def handle(self, *args, **options):

        self.stdout.write("Pulling stuff\n")
        # domain_id = db.view('domain/domains', key="opm", reduce=False).one()['id']
        cases = CommCareCase.get_all_cases('opm') # json
        users = CommCareUser.by_domain('opm') # python
        forms = []
        for u in users:
            forms += u.get_forms().all() # python

        test_data = [form.to_json() for form in forms]
        test_data += [u.to_json() for u in users]
        test_data += cases

        with open(test_data_location, 'w') as f:
            f.write(json.dumps(test_data, indent=2))
            
        self.stdout.write("Pulled stuff, let's hope it worked\n")
