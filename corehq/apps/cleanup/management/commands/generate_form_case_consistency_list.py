from datetime import datetime, timedelta
from optparse import make_option
from django.core.management.base import BaseCommand, LabelCommand
import sys
from casexml.apps.case.models import CommCareCase
from corehq.apps.domain.models import Domain
from corehq.elastic import get_es
from corehq.util.dates import iso_string_to_date
from couchforms.models import XFormInstance
from casexml.apps.case.xform import get_case_ids_from_form

# NOTE: these are referenced by other management commands so don't change
# the names without fixing the references
from dimagi.utils.parsing import json_format_date

HEADERS = [
    'domain',
    'received_on',
    'doc_type',
    'doc_id',
    'case_ids',
    'unmatched_case_ids',
    'xform not in case history?',
]

class Command(BaseCommand):
    args = '<id>'
    help = ('''
        Comprehensive reprocessing command for xforms that had post-submission
        signaling errors that may not have updated the requisite case they were
        attached to''')

    option_list = LabelCommand.option_list + \
                  (
                      make_option('--report',
                                  action='store_true',
                                  dest='do_report',
                                  default=False,
                                  help="Analyze and print a report of the data"),
                      make_option('--from_date',
                                  action='store',
                                  dest='from_date',
                                  default="",
                                  help="Date to begin query range from"),
                  )

    def println(self, message):
        self.stdout.write("%s\n" % message)

    def printerr(self, message):
        self.stderr.write("%s\n" % message)

    def get_all_domains(self):
        db = Domain.get_db()
        return [x['key'] for x in db.view('domain/domains', reduce=False).all()]

    def get_all_submissions(self, domain, from_date):
        #/receiverwrapper/_view/all_submissions_by_domain?startkey=["tulasalud","by_date","2013-03-07"]&endkey=["tulasalud","by_date","2013-05-07"]&reduce=false

        db = XFormInstance.get_db()

        chunk = 500
        start = 0

        sk = [domain, "by_date", json_format_date(from_date)]
        ek = [domain, "by_date", json_format_date(datetime.utcnow() + timedelta(days=10))]

        def call_view(sk, ek, skip, limit):
            return db.view('couchforms/all_submissions_by_domain',
                           startkey=sk,
                           endkey=ek,
                           reduce=False,
                           limit=limit,
                           skip=skip,
                           include_docs=True
            )

        view_chunk = call_view(sk, ek, start, chunk)
        while len(view_chunk) > 0:
            for item in view_chunk:
                if item['doc'] is not None:
                    yield item['doc']
            start += chunk
            view_chunk = call_view(sk, ek, start, chunk)


    def is_case_updated(self, submission, method="couch"):
        # use the same case processing utilities the case code does
        def _case_ids_in_couch(submission):
            case_view = CommCareCase.get_db().view('case/by_xform_id',
                                                   key=submission['_id'],
                                                   reduce=False).all()
            return [row['id'] for row in case_view]

        def _case_ids_in_es(submission):
            query = {
                "filter": {
                    "and": [
                        {"term": {"xform_ids": submission['_id']}}
                    ]
                },
                "from": 0,
                "size":1
            }
            es_results = self.es['hqcases'].post('_search', data=query)
            return [row['_source']['_id'] for row in es_results['hits']['hits']] \
                    if es_results['hits']['hits'] else []

        case_ids_in_form = get_case_ids_from_form(submission)

        case_ids_in_db = set({
            "couch": _case_ids_in_couch,
            "es": _case_ids_in_es,
        }[method](submission))

        missing = case_ids_in_form - case_ids_in_db
        return list(case_ids_in_form), list(missing), bool(missing)

    def handle(self, *args, **options):
        self.es = get_es()
        try:
            from_date = iso_string_to_date(options['from_date'])
        except Exception, ex:
            self.printerr("need a valid date string --from_date YYYY-mm-dd: %s" % ex)
            sys.exit()

        self.println(','.join(HEADERS))
        domains = self.get_all_domains()
        for ix, domain in enumerate(domains):
            self.printerr("Domain: %s (%d/%d)" % (domain, ix, len(domains)))
            for submit in self.get_all_submissions(domain, from_date):
                outrow = [domain, submit['received_on'], submit['doc_type'], submit['_id']]

                # basic case info
                is_dupe=False
                if submit['doc_type'] == 'XFormDuplicate':
                    is_dupe=True
                    orig_submit = XFormInstance.get_db().get(submit['form']['meta']['instanceID'])
                    case_ids, missing, updated = self.is_case_updated(orig_submit)
                else:
                    case_ids, missing, updated = self.is_case_updated(submit)

                if case_ids:
                    outrow.append("|".join(case_ids))
                    outrow.append("|".join(missing))
                    outrow.append(updated)
                else:
                    outrow.append("nocase")
                    outrow.append("|".join(missing)) # would be weird if something was here
                    outrow.append("no update")

                def _should_write():
                    # if we want to make this more configurable can adjust
                    # for now only output if there's a missing case and if
                    # it's not a dupe/deprecated
                    return missing and submit['doc_type'] not in ['XFormDeprecated', 'XFormDuplicate']

                if _should_write():
                    self.println(','.join(str(x) for x in outrow))


