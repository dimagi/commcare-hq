import simplejson
from datetime import datetime, timedelta
from optparse import make_option
from django.core.management.base import BaseCommand, LabelCommand
import sys
from casexml.apps.case.models import CommCareCase
from corehq.apps.domain.models import Domain
from corehq.elastic import get_es
from couchforms.models import XFormInstance
from dimagi.utils.django.management import are_you_sure
from casexml.apps.case.xform import extract_case_blocks
from casexml.apps.case.xml.parser import case_update_from_block


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
        #/receiverwrapper/_view/all_submissions_by_domain?startkey=["tulasalud","by_date","2013-03-07"]&endkey=["tulasalud","by_date","2013-05-07"]&reduce=false

        db = XFormInstance.get_db()

        chunk = 500
        start = 0

        sk = [domain, "by_date", from_date.strftime("%Y-%m-%d")]
        ek = [domain, "by_date", (datetime.utcnow() + timedelta(days=10)).strftime("%Y-%m%d")]

        def call_view(sk, ek, skip, limit):
            return db.view('receiverwrapper/all_submissions_by_domain',
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

        case_blocks = extract_case_blocks(submission)
        case_updates = [case_update_from_block(case_block) for case_block in case_blocks]
        case_ids_in_form = set(cu.id for cu in case_updates)

        case_ids_in_db = set({
            "couch": _case_ids_in_couch,
            "es": _case_ids_in_es,
        }[method](submission))

        missing = case_ids_in_form - case_ids_in_db
        return list(case_ids_in_form), list(missing), bool(missing)

    def handle(self, *args, **options):
        self.es = get_es()
        do_process = options['do_process']
        try:
            from_date = datetime.strptime(options['from_date'], "%Y-%m-%d")
        except Exception, ex:
            self.printerr("need a valid date string --from_date YYYY-mm-dd: %s" % ex)
            sys.exit()

        if do_process:
            if not are_you_sure("""
Are you sure you want to make written changes to the database?
Type 'yes' to continue, or 'no' to cancel: """):
                self.printerr("You didn't say yes, so we're quitting, chicken.")
                sys.exit()
            else:
                self.printerr("OK, proceeding, I hope you know what you're doing")
                self.printerr("Just kidding, this is still way to dangerous!")
                # TODO: call the real cleanup command here
                sys.exit()

        headers = [
            'domain',
            'received_on',
            'doc_type',
            'doc_id',
            'case_ids',
            'unmatched_case_ids',
            'xform in case history?',
            'orig doc_id if dupe',
            'subcases'
        ]
        self.println(','.join(headers))
        domains = self.get_all_domains()
        for ix, domain in enumerate(domains):
            self.printerr("Domain: %s (%d/%d)" % (domain, ix, len(domains)))
            for submit in self.get_all_submissions(domain, from_date):
                outrow = [domain, submit['received_on'], submit['doc_type'], submit['_id']]

                #basic case info
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
                if is_dupe:
                    outrow.append(orig_submit['_id'])
                else:
                    outrow.append("not dupe")

                #check subcases being updated? not checked now todo if necessary
                subcase_keys = filter(lambda x: x.startswith('subcase_'), submit['form'].keys())
                try:
                    #outrow += [submit['form'][k].get('case',{}).get('@case_id','nosubcaseid') for k in subcase_keys]
                    for k in subcase_keys:
                        subcase_data = submit['form'][k]
                        if isinstance(subcase_data, dict):
                            outrow.append(subcase_data.get('case',{}).get('@case_id','nosubcaseid'))
                except Exception, ex:
                    print "error, fix it %s" % ex
                    print outrow
                    print subcase_keys
                    print simplejson.dumps(submit['form'], indent=4)
                    sys.exit()
                self.println(','.join(str(x) for x in outrow))


