from optparse import make_option
from couchdbkit import ResourceNotFound
from django.core.management.base import BaseCommand
from casexml.apps.case.cleanup import rebuild_case
from casexml.apps.case.models import CommCareCase
from corehq.elastic import stream_es_query, ES_URLS
import dateutil.parser as dparser


def forms_with_cases(domain=None, since=None):
    q = {"filter": {"and": [{"bool": {
            "must_not": {
               "missing": {
                    "field": "form.case.@case_id",
                    "existence": True,
                    "null_value": True}}}}]}}
    params={"domain.exact": domain} if domain else {}
    if since:
        q["filter"]["and"][0]["bool"]["must"] = {
            "range": {
                "received_on": {"from": since.strftime("%Y-%m-%d")}}}
    return stream_es_query(params=params, q=q, es_url=ES_URLS["forms"], fields=["form.case.@case_id"])

def check_case_for_form_updates(form_id, case_id):
    print "checking case (%s) for form (%s)" % (case_id, form_id)
    ret, error, case = False, "", None
    try:
        case = CommCareCase.get(case_id)
        ret = case.form_in_actions(form_id)
        if not ret:
            error = "action_missing"
    except ResourceNotFound:
        error = "nonexistent_case"
    return { "valid": ret, "error": error, "case": case}


class Command(BaseCommand):
    args = '<domain>'
    help = ('Checks all forms in a domain to make sure their cases were properly updated.')

    option_list = BaseCommand.option_list + (
        make_option('-s', '--since',
            help="Begin check at this date."),
        make_option('-r', '--rebuild', action="store_true",
            help="Rebuild cases that were found to be corrupt"),
        )

    def handle(self, *args, **options):
        domain = args[0] if len(args) == 1 else None
        since = dparser.parse(options["since"], fuzzy=True) if options.get("since") else None
        rebuild = options.get("rebuild")

        for form in forms_with_cases(domain, since):
            form_id, case_ids = form["_id"], form["fields"]["form.case.@case_id"]
            case_ids = [case_ids] if isinstance(case_ids, basestring) else case_id
            for case_id in case_ids:
                validation = check_case_for_form_updates(form_id, case_id)
                if not validation["valid"]:
                    if validation["error"] == "nonexistent_case":
                        print "Case (%s) from form (%s) does not exist" % (case_id, form_id)
                    elif validation["error"] == "action_missing":
                        print "Case (%s) missing action for form (%s)" % (case_id, form_id)
                    if rebuild:
                        print "rebuilding case (%s) from scratch" % case_id
                        try:
                            rebuild_case(validation["case"] or case_id)
                        except Exception as e:
                            print "Case Rebuild Failure: %s" % e
