import json

from django.core.management.base import BaseCommand
from corehq.apps.users.models import CommCareUser, CommCareCase
from dimagi.utils.couch.database import get_db

from custom.opm.opm_reports.tests import test_data_location
from custom.opm.opm_reports.beneficiary import Beneficiary
from custom.opm.opm_reports.incentive import Worker


class Command(BaseCommand):
    """
    Generate test data for the OPM reports.
    It pulls stuff from the db, runs the report, then saves it as a json file.
    There's no intelligent testing going on, but it can at least verify
    consistency.
    """
    help = "Pull data from the database and write\
        to a json file (currently only works for opm"

    def get_beneficiary_results(self, case):
        beneficiary = Beneficiary(case)
        results = []
        for method, name in beneficiary.method_map:
            results.append((method, getattr(beneficiary, method)))
        return results

    def get_test_results(self, item, model):
        instance = model(item)
        results = []
        for method, name in model.method_map:
            results.append((method, getattr(instance, method)))
        return results

    def handle(self, *args, **options):

        self.stdout.write("Pulling stuff\n")
        beneficiaries = CommCareCase.get_all_cases('opm', include_docs=True)
        users = CommCareUser.by_domain('opm')
        forms = []

        for b in beneficiaries:
            forms += b.get_forms()
            # add Beneficiary test results
            b.test_results = self.get_beneficiary_results(b)

        # add Incentive test results
        for u in users:
            u.test_results = self.get_test_results(u, Worker)

        test_data = [form.to_json() for form in forms]
        test_data += [u.to_json() for u in users]
        test_data += [b.to_json() for b in beneficiaries]

        doc_ids = set()
        docs = []
        for doc in test_data:
            if doc['_id'] not in doc_ids:
                for attrib in ['_rev', '_attachments']:
                    try:
                        del doc[attrib]
                    except KeyError:
                        pass                
                doc_ids.add(doc['_id'])
                docs.append(doc)
            else:
                self.stdout.write("Ignoring duplicates\n")

        with open(test_data_location, 'w') as f:
            f.write(json.dumps(docs, indent=2))
            
        self.stdout.write("Pulled stuff, let's hope it worked\n")
