from datetime import datetime, timedelta
from optparse import make_option
from django.core.management.base import BaseCommand, CommandError, LabelCommand
import sys
from casexml.apps.case.models import CommCareCase
from corehq.apps.cleanup.xforms import reprocess_form_cases
from corehq.apps.domain.models import Domain
from corehq.elastic import get_es
from couchforms.models import XFormError, XFormInstance


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

    def get_all_domains(self):
        db = Domain.get_db()
        return [x['key'] for x in db.view('domain/domains', reduce=False).all()]

    def get_all_submissions(self, domain, from_date):
        #/receiverwrapper/_view/all_submissions_by_domain?startkey=["tulasalud","by_date","2013-03-07"]&endkey=["tulasalud","by_date","2013-05-07"]&reduce=false

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
                #case_doc = CommCareCase.get(case_id)
                query = {
                    "filter": {
                        "and": [
                            {"term": {"domain.exact": submission['domain']}},
                            {"term": {"xform_id": submission['_id']}}
                        ]
                    },
                    "from": 0,
                    "size":1
                }
                es_results = self.es['hqcases'].post('_search', data=query)
                for row in es_results['hits']['hits']:
                    case_doc = row['_source']
                    print case_doc['_id']
                    return case_id, True
                return case_id, False
            else:
                return None, None



    def handle(self, *args, **options):
        self.es = get_es()
        do_process = options['do_process']
        try:
            from_date = datetime.strptime(options['from_date'], "%Y-%m-%d")
        except Exception, ex:
            print "need a valid date string --from_date YYYY-mm-dd: %s" % ex
            sys.exit()

        if do_process:
            confirm = raw_input("""
Are you sure you want to make written changes to the database?
Type 'yes' to continue, or 'no' to cancel: """)
            pass

            if confirm == "yes":
                print "OK, proceeding, I hope you know what you're doing"
                sys.exit()
            else:
                print "You didn't say yes, so we're quitting, chicken."
                sys.exit()


        #time for analysis
        domains = self.get_all_domains()
        for domain in domains:
            print "Starting domain query: %s" % domain
            xform_submissions = self.get_all_submissions(domain, from_date)
            for submit in xform_submissions:
                outrow = [submit['received_on'], submit['doc_type'], submit['_id']]
                case_id, updated = self.is_case_updated(submit)
                if case_id:
                    outrow.append(case_id)
                    outrow.append(updated)
                else:
                    outrow.append("")
                    outrow.append("")
                print ",".join(outrow)



