from gevent import monkey; monkey.patch_all()
import sys
import gevent
from restkit.session import set_session
set_session("gevent")

from couchdbkit.exceptions import ResourceNotFound
from django.core.management.base import LabelCommand
from casexml.apps.case.models import CommCareCase
from corehq.apps.indicators.models import CaseIndicatorDefinition, FormIndicatorDefinition, DocumentMismatchError, DocumentNotInDomainError
from couchforms.models import XFormInstance
from dimagi.utils.couch.database import get_db
from dimagi.utils.management.commands import prime_views
from mvp.models import MVP

class Command(LabelCommand):
    help = "Update MVP indicators in existing cases and forms."
    args = "<indicator type> <case type or xmlns>"
    label = ""

    def handle(self, *args, **options):
        do_forms = True
        do_cases = True
        specific_case_or_form = None
        if len(args) > 0:
            indicator_type = args[0]
            if 'all' in indicator_type:
                pass
            elif 'forms' in indicator_type:
                do_cases = False
            elif 'cases' in indicator_type:
                do_forms = False
            if len(args) > 1:
                specific_case_or_form = args[1]

        if do_forms:
            if specific_case_or_form:
                print "\n\n Getting Forms With XMLNS: %s" % specific_case_or_form
                self.update_indicators_for_xmlns(specific_case_or_form)
            else:
                for form_slug, xmlns in MVP.CLOSE_FORMS.items():
                    print "\n\nGetting Close Forms of Type %s" % form_slug
                    self.update_indicators_for_xmlns(xmlns)
                for form_slug, xmlns in MVP.VISIT_FORMS.items():
                    print "\n\nGetting Visit Forms of Type %s" % form_slug
                    self.update_indicators_for_xmlns(xmlns)

        if do_cases:
            case_types = ['child', 'pregnancy', 'household']
            if specific_case_or_form:
                case_types = [specific_case_or_form]
            for type in case_types:
                for domain in MVP.DOMAINS:
                    self.update_indicators_for_case_type(type, domain)

    def update_indicators_for_xmlns(self, xmlns):
        relevant_forms = get_db().view("couchforms/by_xmlns",
            reduce=True,
            key=xmlns
        ).first()
        num_forms = relevant_forms['value'] if relevant_forms else 0

        get_forms = lambda skip, limit: XFormInstance.view("couchforms/by_xmlns",
            reduce=False,
            include_docs=True,
            key=xmlns,
            skip=skip,
            limit=limit
        ).all()

        print "Found %d forms with matching XMLNS %s" % (num_forms, xmlns)
        for domain in MVP.DOMAINS:
            relevant_indicators = FormIndicatorDefinition.get_all(
                namespace=MVP.NAMESPACE,
                domain=domain,
                xmlns=xmlns
            )
            if relevant_indicators:
                self._throttle_updates("Forms (XMLNS %s, DOMAIN: %s)" % (xmlns, domain),
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
        for indicator in indicators:
            print "Indicator %s v.%d, %s" % (indicator.slug, indicator.version, domain)
            errors = list()
            success = list()
            for doc in docs:
                try:
                    is_update = doc.update_indicator(indicator)
                    if is_update:
                        success.append(doc.get_id)
                        sys.stdout.write("N")
                    else:
                        sys.stdout.write(".")
                except ResourceNotFound:
                    sys.stdout.write("R")
                except (DocumentMismatchError, DocumentNotInDomainError):
                    sys.stdout.write('-')
                except Exception as e:
                    errors.append(e)
                    sys.stdout.write('!')
                sys.stdout.flush()
            if errors:
                print "There were %d errors updating indicator %s" % (len(errors), indicator.slug)
                print "\n".join(["%s" % e for e in errors])
            print "\n"

    def _throttle_updates(self, document_type, indicators, total_docs, domain, get_docs, limit=100):
        for skip in range(0, total_docs, limit):
            print "\n\nUpdating %s %d to %d of %d\n" % (document_type, skip, min(total_docs, skip+limit), total_docs)
            matching_docs = get_docs(skip, limit)
            self.update_indicators(indicators, matching_docs, domain)
            print "Priming views."
            prime_all = prime_views.Command()
            prime_all.prime_everything()
            print "\nViews have been primed."
