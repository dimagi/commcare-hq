from datetime import datetime, timedelta
from optparse import make_option
import sys

from django.core.management.base import BaseCommand, LabelCommand

from corehq.apps.domain.models import Domain
from corehq.elastic import get_es
from couchforms.models import XFormInstance


class Command(BaseCommand):
    args = '<id>'
    help = (
        'Comprehensive reprocessing command for xforms that had post-submission signaling errors that may not have updated the requisite case they were attached to')

    option_list = LabelCommand.option_list + \
                  (
                      make_option('--report',
                                  action='store_true',
                                  dest='do_report',
                                  default=False,
                                  help="Analyze and print a report of the data"),
                      make_option('--do_processing',
                                  action='store_true',
                                  dest='do_process',
                                  default=False,
                                  help="Actually do the processing"),
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
        #/receiverwrapper/_view/all_submissions_by_domain?startkey=["domain","by_date","2013-03-07"]&endkey=["domain","by_date","2013-05-07"]&reduce=false

        db = XFormInstance.get_db()

        chunk = 500
        start = 0
        end = chunk

        sk = [domain, "by_date", from_date.strftime("%Y-%m-%d")]
        ek = [domain, "by_date", (datetime.utcnow() + timedelta(days=10)).strftime("%Y-%m%d")]

        def call_view(sk, ek, s, l):
            return db.view('receiverwrapper/all_submissions_by_domain',
                           startkey=sk,
                           endkey=ek,
                           reduce=False,
                           limit=l,
                           skip=s,
                           include_docs=True
            )

        view_chunk = call_view(sk, ek, start, chunk)
        while len(view_chunk) > 0:
            for item in view_chunk:
                if item['doc'] is not None:
                    yield item['doc']
            start += chunk
            view_chunk = call_view(sk, ek, start, chunk)

    def is_case_updated(self, submission):
        case_id = None
        if 'case' in submission['form']:
            if '@case_id' in submission['form']['case']:
                case_id = submission['form']['case']['@case_id']
            if 'case_id' in submission['form']['case']:
                case_id = submission['form']['case']['case_id']

            if case_id is not None:
                query = {
                    "filter": {
                        "and": [
                            {"term": {"domain.exact": submission['domain']}},
                            {"term": {"xform_ids": submission['_id']}}
                        ]
                    },
                    "from": 0,
                    "size":1
                }
                es_results = self.es['hqcases'].post('_search', data=query)
                if es_results['hits']['hits']:
                    for row in es_results['hits']['hits']:
                        case_doc = row['_source']
                        #print case_doc['_id']
                        return case_id, True
                return case_id, False
            else:
                return None, None
        else:
            return None, None

    def handle(self, *args, **options):
        self.es = get_es()
        do_process = options['do_process']
        try:
            from_date = datetime.strptime(options['from_date'], "%Y-%m-%d")
        except Exception, ex:
            self.printerr("need a valid date string --from_date YYYY-mm-dd: %s" % ex)
            sys.exit()

        if do_process:
            confirm = raw_input("""
Are you sure you want to make written changes to the database?
Type 'yes' to continue, or 'no' to cancel: """)
            pass

            if confirm == "yes":
                self.printerr("OK, proceeding, I hope you know what you're doing")
                sys.exit()
            else:
                self.printerr("You didn't say yes, so we're quitting, chicken.")
                sys.exit()

        #time for analysis
        domains = self.get_all_domains()
        for domain in domains:
            self.printerr("Starting domain query: %s" % domain)
            for submit in self.get_all_submissions(domain, from_date):
                outrow = [domain, submit['received_on'], submit['doc_type'], submit['_id']]
                if submit['doc_type'] == 'XFormDuplicate':
                    #for dupes, actually check the "real" submit and see if that case has been updated
                    orig_submit = XFormInstance.get_db().get(submit['form']['meta']['instanceID'])
                    case_id, updated = self.is_case_updated(orig_submit)
                else:
                    case_id, updated = self.is_case_updated(submit)
                if case_id:
                    outrow.append(case_id)
                    outrow.append(updated)
                else:
                    outrow.append("")
                    outrow.append("")
                if submit['doc_type'] == 'XFormDuplicate':
                    #append orig id this is a dupe of at the end
                    outrow.append(orig_submit['_id'])
                self.println(','.join(str(x) for x in outrow))
