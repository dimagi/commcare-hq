from datetime import datetime
import os, json, string

from django.http import HttpRequest
from django.test import TestCase

from fluff.management.commands.ptop_fast_reindex_fluff import FluffPtopReindexer

from corehq.apps.users.models import WebUser
from corehq.apps.users.models import CommCareUser, CommCareCase
from dimagi.utils.couch.database import get_db
from dimagi.utils.modules import to_function

from custom.opm.opm_tasks.tasks import save_report
from custom.opm.opm_tasks.models import OpmReportSnapshot
from ..constants import *
from ..beneficiary import Beneficiary
from ..reports import (BeneficiaryPaymentReport, IncentivePaymentReport,
    get_report)
from ..models import (OpmUserFluff, OpmCaseFluffPillow,
    OpmUserFluffPillow, OpmFormFluffPillow)

DIR_PATH = os.path.abspath(os.path.dirname(__file__))
test_data_location = os.path.join(DIR_PATH, 'opm_test.json')
test_month_year = (8, 2013)

fixtures_loaded = False


class OPMTestBase(object):

    def load_test_data(self):
        print "loading test data"
        with open(test_data_location) as f:
            docs = json.loads(f.read())
        for doc in docs:
            self.db.save_doc(doc)

    def reindex_fluff(self, pillow):
        flufftop = FluffPtopReindexer()
        dotpath = '.'.join([OpmUserFluff.__module__, pillow.__name__])
        print dotpath
        flufftop.pillow_class = to_function(dotpath)
        flufftop.domain = DOMAIN
        flufftop.resume = False
        flufftop.bulk = False
        flufftop.db = flufftop.doc_class.get_db()
        flufftop.runfile = None
        flufftop.start_num = 0
        flufftop.chunk_size = 500
        flufftop.pillow = flufftop.pillow_class(chunk_size=0)
        for i, row in enumerate(flufftop.full_couch_view_iter()):
            print "\tProcessing item %s (%d)" % (row['id'], i)
            flufftop.process_row(row, i)

    def setUp(self):
        global fixtures_loaded
        if not fixtures_loaded:
            fixtures_loaded = True
            self.db = get_db()
            self.load_test_data()
            for pillow in [OpmCaseFluffPillow, OpmUserFluffPillow, OpmFormFluffPillow]:
                self.reindex_fluff(pillow)
        print "Finished setup, on to tests!"

    def the_same(self, a, b):
        # for some reason types aren't consistent
        # so there's this beautiful kludge
        if a == b:
            return True
        try:
            if str(a) == str(b):
                return True
        except:
            print "|%s| is not the same as |%s|" % (a, b)
            pass
        return False

    def test_all_results(self):
        print "%s Tests:" % self.ReportClass.__name__
        month, year = test_month_year
        # report produced from test data
        report = get_report(self.ReportClass, month, year)
        # saved report snapshot
        snapshot = OpmReportSnapshot.by_month(month, year,
            self.ReportClass.__name__)
        errors = []
        total = len(snapshot.rows)

        name_index = snapshot.slugs.index('name')
        def stringify(row):
            string_row = []
            for element in row:
                element = element or ""
                try:
                    str(element)
                except:
                    string_row.append(element)
                else:
                    string_row.append(str(element))
            return string_row

        report_rows = sorted(report.rows, key=stringify)
        self.assertEquals(total, len(report_rows),
            "different number of rows for %s" % self.ReportClass.__name__)
        for i, snapshot_row in enumerate(sorted(snapshot.rows, key=stringify)):
            report_row = report_rows[i]
            for snapshot_index, slug in enumerate(snapshot.slugs):
                report_index = report.slugs.index(slug)
                snapshot_item = snapshot_row[snapshot_index] or ""
                report_item = report_row[report_index] or ""
                if not self.the_same(snapshot_item, report_item):
                    errors.append('%s \t"%s" != "%s" \t%s' %
                        (slug, snapshot_item, report_item, report_row[name_index]))
        self.assertEquals(errors, [], "\n\n" + '\n'.join(errors))


# class TestIncentive(OPMTestBase, TestCase):
    # ReportClass = IncentivePaymentReport

# class TestBeneficiary(OPMTestBase, TestCase):
    # ReportClass = BeneficiaryPaymentReport


# class TestBuildOPM(OPMTestBase, TestCase):
#     """
#     uncomment this class to rebuild test json
#     """
#     def load_test_data(self):
#         with open(test_data_location) as f:
#             docs = json.loads(f.read())
#
#         self.out_docs = []
#         self.validate_docs(docs)
#
#         for doc in self.out_docs:
#             self.db.save_doc(doc)
#
#     def validate_docs(self, docs):
#         for doc in docs:
#             if doc['doc_type'] == 'OpmReportSnapshot':
#                 continue
#             if doc['doc_type'] == "CommCareCase":
#                 pass
#             elif doc['doc_type'] == "XFormInstance":
#                 if doc['xmlns'] not in [
#                     PREG_REG_XMLNS,
#                     BIRTH_PREP_XMLNS,
#                     DELIVERY_XMLNS,
#                     CHILD_FOLLOWUP_XMLNS,
#                     CFU1_XMLNS,
#                     CFU2_XMLNS,
#                     CFU3_XMLNS,
#                 ]:
#                     print "removing bad form"
#                     continue
#             self.out_docs.append(doc)
#
#     def test_all_results(self):
#         month, year = test_month_year
#         incentive_report = save_report(IncentivePaymentReport, month, year)
#         beneficiary_report = save_report(BeneficiaryPaymentReport, month, year)
#         print "*"*40
#         print "writing! output"
#         print "bp report is %s rows" % len(beneficiary_report.rows)
#         print "*"*40
#         self.out_docs.append(incentive_report.to_json())
#         self.out_docs.append(beneficiary_report.to_json())
#         with open('opm_test_docs.json', 'w') as f:
#             f.write(json.dumps(self.out_docs, indent=2))
