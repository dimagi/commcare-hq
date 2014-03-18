from gevent import monkey;
import time

monkey.patch_all()
import sys
import gevent
from restkit.session import set_session
set_session("gevent")
from gevent.pool import Pool

from couchdbkit.exceptions import ResourceNotFound
from django.core.management.base import LabelCommand
from casexml.apps.case.models import CommCareCase
from corehq.apps.indicators.models import CaseIndicatorDefinition, FormIndicatorDefinition, DocumentMismatchError, DocumentNotInDomainError
from couchforms.models import XFormInstance
from dimagi.utils.couch.database import get_db
from dimagi.utils.management.commands import prime_views
from mvp.models import MVP

POOL_SIZE = 10

class Command(LabelCommand):
    help = "Update MVP indicators in existing cases and forms."
    args = "<domain> <case or form> <case or form label> <start at record #>"
    label = ""
    start_at_record = 0
    domains = None

    def handle(self, *args, **options):
        self.domains = [args[0]] if len(args) > 0 and args[0] != "all" else MVP.DOMAINS

        cases = ['child', 'pregnancy', 'household']

        process_forms = True
        process_cases = True

        self.start_at_record = int(args[3]) if len(args) > 3 else 0

        if len(args) > 1 and args[1] != "all":
            document = args[1]
            process_cases = document == "case"
            process_forms = document == "form"

        if len(args) > 2 and args[2] != "all":
            document_type = args[2]
            if process_cases:
                cases = [document_type]
        else:
            document_type = None


        if process_forms:
            for domain in self.domains:
                self.update_indicators_for_xmlns(domain, form_label_filter=document_type)

        if process_cases:
            for case_type in cases:
                for domain in self.domains:
                    self.update_indicators_for_case_type(case_type, domain)

    def update_indicators_for_xmlns(self, domain, form_label_filter=None):
        key = [MVP.NAMESPACE, domain]
        all_labels = get_db().view('indicators/form_labels',
            reduce=False,
            startkey=key,
            endkey=key + [{}],
        ).all()
        for label in all_labels:
            label_name = label['value']
            if form_label_filter is not None and form_label_filter != label_name:
                continue
            xmlns = label['key'][-2]
            print "\n\nGetting Forms of Type %s and XMLNS %s for domain %s" % (label_name, xmlns, domain)

            relevant_forms = get_db().view("reports_forms/all_forms",
                reduce=True,
                startkey=['submission xmlns', domain, xmlns],
                endkey=['submission xmlns', domain, xmlns, {}],
            ).first()
            num_forms = relevant_forms['value'] if relevant_forms else 0
            get_forms = lambda skip, limit: XFormInstance.view("reports_forms/all_forms",
                reduce=False,
                include_docs=True,
                startkey=['submission xmlns', domain, xmlns],
                endkey=['submission xmlns', domain, xmlns, {}],
                skip=skip,
                limit=limit
            ).all()

            print "Found %d forms with matching XMLNS %s" % (num_forms, xmlns)
            relevant_indicators = FormIndicatorDefinition.get_all(
                namespace=MVP.NAMESPACE,
                domain=domain,
                xmlns=xmlns
            )
            if relevant_indicators:
                self._throttle_updates("Forms (TYPE: %s, XMLNS %s, DOMAIN: %s)" % (label_name, xmlns, domain),
                                       relevant_indicators, num_forms, domain, get_forms)


    def update_indicators_for_case_type(self, case_type, domain):
        print "\n\n\nFetching %s cases in domain %s...." % (case_type, domain)
        key = ["all type", domain, case_type]
        relevant_indicators = CaseIndicatorDefinition.get_all(
            namespace=MVP.NAMESPACE,
            domain=domain,
            case_type=case_type
        )

        if relevant_indicators:
            all_cases = get_db().view("case/all_cases",
                reduce=True,
                startkey=key,
                endkey=key+[{}]
            ).first()
            num_cases = all_cases['value'] if all_cases else 0

            print "\nFound the following Case Indicator Definitions for Case Type %s in Domain %s" % (case_type, domain)
            print "--%s\n" % "\n--".join([i.slug for i in relevant_indicators])

            print "Found %d possible cases for update." % num_cases
            get_cases = lambda skip, limit: CommCareCase.view("case/all_cases",
                reduce=False,
                include_docs=True,
                startkey=key,
                endkey=key+[{}],
                skip=skip,
                limit=limit
            ).all()
            self._throttle_updates("Cases of type %s in %s" % (case_type, domain),
                                   relevant_indicators, num_cases, domain, get_cases)

    def update_indicators(self, indicators, docs, domain):

        def _update_doc(doc):
            try:
                is_update = doc.update_indicator(indicator)
                if is_update:
                    sys.stdout.write("N")
                else:
                    sys.stdout.write(".")
            except ResourceNotFound:
                sys.stdout.write("R")
            except (DocumentMismatchError, DocumentNotInDomainError):
                sys.stdout.write('-')
            except Exception as e:
                sys.stdout.write('!')
            sys.stdout.flush()

        for indicator in indicators:
            print "Indicator %s v.%d, %s" % (indicator.slug, indicator.version, domain)
            pool = Pool(POOL_SIZE)
            for doc in docs:
                pool.spawn(_update_doc, doc)
            pool.join() # blocking
            print "\n"

    def _throttle_updates(self, document_type, indicators, total_docs, domain, get_docs, limit=300):

        for skip in range(self.start_at_record, total_docs, limit):
            print "\n\nUpdating %s %d to %d of %d\n" % (document_type, skip, min(total_docs, skip+limit), total_docs)
            matching_docs = get_docs(skip, limit)
            self.update_indicators(indicators, matching_docs, domain)
            print "Pausing..."
            time.sleep(3)
            print "Going..."
