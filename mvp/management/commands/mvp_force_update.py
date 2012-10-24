import logging
from couchdbkit.exceptions import ResourceNotFound
from django.core.management.base import LabelCommand
import sys
from casexml.apps.case.models import CommCareCase
from corehq.apps.indicators.models import CaseIndicatorDefinition, FormIndicatorDefinition, DocumentMistmatchError, DocumentNotInDomainError
from couchforms.models import XFormInstance
from dimagi.utils.couch.database import get_db
from mvp.models import MVP, MVPCannotFetchCaseError

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
                for form_slug, xmlns in MVP.VISIT_FORMS.items():
                    print "\n\nGetting Forms of Type %s" % form_slug
                    self.update_indicators_for_xmlns(xmlns)

        if do_cases:
            case_types = ['child', 'pregnancy', 'household']
            if specific_case_or_form:
                case_types = [specific_case_or_form]
            for type in case_types:
                for domain in MVP.DOMAINS:
                    self.update_indicators_for_case_type(type, domain)

    def update_indicators_for_xmlns(self, xmlns):
        relevant_forms = XFormInstance.view("couchforms/by_xmlns",
            reduce=False,
            include_docs=True,
            key=xmlns
        ).all()
        print "Found %d forms with matching XMLNS %s" % (len(relevant_forms), xmlns)
        for domain in MVP.DOMAINS:
            relevant_indicators = FormIndicatorDefinition.get_all(
                namespace=MVP.NAMESPACE,
                domain=domain,
                xmlns=xmlns
            )
            print "\nUpdating Form Indicators for Domain %s" % domain
            print "--%s\n" % "\n--".join([i.slug for i in relevant_indicators])
            self.update_indicators(relevant_indicators, relevant_forms, domain)

    def update_indicators_for_case_type(self, case_type, domain):
        print "\n\n\nFetching %s cases in domain %s...." % (case_type, domain)
        key = ["all type", domain, case_type]
        relevant_indicators = CaseIndicatorDefinition.get_all(
            namespace=MVP.NAMESPACE,
            domain=domain,
            case_type=case_type
        )
        if relevant_indicators:
            # do cases in chunks
            num_matching_cases = get_db().view("case/all_cases",
                reduce=True,
                startkey=key,
                endkey=key+[{}]
            ).first().get('value', 0)
            print "Found %d possible cases for update." % num_matching_cases

            print "\nFound the following Case Indicator Definitions for Case Type %s in Domain %s" % (case_type, domain)
            print "--%s\n" % "\n--".join([i.slug for i in relevant_indicators])

            limit = 100
            for skip in range(0, num_matching_cases, limit):
                print "Updating Cases %d to %d of %d" % (skip, min(num_matching_cases, skip+limit), num_matching_cases)
                relevant_cases = CommCareCase.view("case/all_cases",
                    reduce=False,
                    include_docs=True,
                    startkey=key,
                    endkey=key+[{}],
                    skip=skip,
                    limit=limit
                ).all()
                self.update_indicators(relevant_indicators, relevant_cases, domain)

    def update_indicators(self, indicators, docs, domain):
        for indicator in indicators:
            print "--\nIndicators defined by %s | Domain '%s'" % (indicator.slug, domain)
            errors = list()
            success = list()
            for doc in docs:
                try:
                    doc.set_definition(indicator)
                    doc.save()
                    success.append(doc.get_id)
                    sys.stdout.write(".")
                except ResourceNotFound:
                    sys.stdout.write("R")
                except (DocumentMistmatchError, MVPCannotFetchCaseError, DocumentNotInDomainError):
                    sys.stdout.write('-')
                except Exception as e:
                    errors.append(e)
                    sys.stdout.write('!')
                sys.stdout.flush()
            print "\n%d out of %d documents were updated." % (len(success), len(docs))
            if errors:
                print "There were %d errors updating indicator %s" % (len(errors), indicator.slug)
                print "\n".join(["%s" % e for e in errors])
            print "\n"
