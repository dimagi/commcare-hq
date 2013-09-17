import json

from django.core.management.base import BaseCommand

from corehq.apps.users.models import CommCareUser, CommCareCase
from corehq.apps.fixtures.models import FixtureDataItem
from dimagi.utils.couch.database import get_db

from custom.opm.opm_reports.tests import test_data_location, test_month_year
from custom.opm.opm_reports.beneficiary import Beneficiary
from custom.opm.opm_reports.constants import DOMAIN
from custom.opm.opm_reports.incentive import Worker
from custom.opm.opm_reports.reports import (BeneficiaryPaymentReport,
    IncentivePaymentReport, get_report)
from custom.opm.opm_tasks.models import OpmReportSnapshot


class Command(BaseCommand):
    """
    Generate test data for the OPM reports.
    It pulls stuff from the db and saves it as a json file.
    It also runs reports, saves a snapshot, and stores that in the json file
    There's no intelligent testing going on, but it can at least verify
    consistency.
    """
    help = "Pull data from the database and write\
        to a json file (currently only works for opm)"

    def handle(self, *args, **options):

        self.stdout.write("Pulling stuff\n")
        beneficiaries = CommCareCase.get_all_cases('opm', include_docs=True)
        users = CommCareUser.by_domain('opm')
        fixtures = FixtureDataItem.get_item_list('opm', 'condition_amounts')
        forms = []

        for b in beneficiaries:
            forms += b.get_forms()

        test_data = []

        month, year = test_month_year
        for report_class in [IncentivePaymentReport, BeneficiaryPaymentReport]:
            self.stdout.write("Running %s\n" % report_class.__name__)
            report = get_report(report_class, month, year)
            snapshot = OpmReportSnapshot(
                domain=DOMAIN,
                month=month,
                year=year,
                report_class=report.report_class.__name__,
                headers=report.headers,
                slugs=report.slugs,
                rows=report.rows,
            )
            test_data.append(snapshot.to_json())

        self.stdout.write("Saving raw data\n")
        test_data += [form.to_json() for form in forms]
        test_data += [u.to_json() for u in users]
        test_data += [b.to_json() for b in beneficiaries]
        test_data += [f.to_json() for f in fixtures]

        doc_ids = set()
        docs = []
        for doc in test_data:
            if doc.get('_id') not in doc_ids:
                for attrib in ['_rev', '_attachments']:
                    try:
                        del doc[attrib]
                    except KeyError:
                        pass                
                doc_ids.add(doc.get('_id', 'null'))
                docs.append(doc)
            else:
                self.stdout.write("Ignoring duplicates\n")

        with open(test_data_location, 'w') as f:
            f.write(json.dumps(docs, indent=2))
            
        self.stdout.write("Pulled stuff, let's hope it worked\n")
