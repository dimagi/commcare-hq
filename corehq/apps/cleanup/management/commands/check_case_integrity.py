from optparse import make_option
from couchdbkit import ResourceNotFound
from django.core.management.base import BaseCommand
from casexml.apps.case.cleanup import rebuild_case
from casexml.apps.case.models import CommCareCase
from corehq.elastic import stream_es_query, ES_URLS
import dateutil.parser as dparser
import csv


def forms_with_cases(domain=None, since=None):
    q = {"filter": {"and": [{"bool": {
            "must_not": {
               "missing": {
                    "field": "__retrieved_case_ids",
                    "existence": True,
                    "null_value": True}}}}]}}
    params={"domain.exact": domain} if domain else {}
    if since:
        q["filter"]["and"][0]["bool"]["must"] = {
            "range": {
                "received_on": {"from": since.strftime("%Y-%m-%d")}}}
    return stream_es_query(params=params, q=q, es_url=ES_URLS["forms"], fields=["__retrieved_case_ids", "domain"])

def check_case_for_form_updates(form_id, case_id, verbose=False):
    if verbose:
        print "checking case (%s) for form (%s)" % (case_id, form_id)
    ret, error, case = False, "", None
    try:
        case = CommCareCase.get(case_id)
        ret = case.form_in_actions(form_id)
        if not ret:
            error = "action_missing"
    except ResourceNotFound:
        error = "nonexistent_case"
    return {"valid": ret, "error": error, "case": case}


class Command(BaseCommand):
    args = '<domain>'
    help = ('Checks all forms in a domain to make sure their cases were properly updated.')

    option_list = BaseCommand.option_list + (
        make_option('-s', '--since',
            help="Begin check at this date."),
        make_option('-f', '--filename',
            help="Begin check at this date."),
        make_option('-r', '--rebuild', action="store_true",
            help="Rebuild cases that were found to be corrupt"),
        make_option('--verbose', action="store_true",
            help="Verbose"),
        )

    def handle(self, *args, **options):
        domain = args[0] if len(args) == 1 else None
        since = dparser.parse(options["since"], fuzzy=True) if options.get("since") else None
        filename = options.get("filename") or ("case_integrity" + ("_%s" % domain if domain else ""))
        if not filename.endswith(".csv"):
            filename = "%s.csv" % filename
        rebuild, verbose = options.get("rebuild"), options.get("verbose")
        print "writing to file: %s" % filename

        with open(filename, 'wb+') as csvfile:
            csv_writer = csv.writer(csvfile, delimiter=' ',
                                    quotechar='|', quoting=csv.QUOTE_MINIMAL)
            csv_writer.writerow(['Domain', 'Case ID', 'Form ID', 'Error'])

            for form in forms_with_cases(domain, since):
                form_id, case_ids, f_domain = form["_id"], form["fields"]["__retrieved_case_ids"], form["fields"]["domain"]
                case_ids = [case_ids] if isinstance(case_ids, basestring) else case_ids
                for case_id in case_ids:
                    validation = check_case_for_form_updates(form_id, case_id, verbose)
                    if not validation["valid"]:
                        csv_writer.writerow([f_domain, case_id, form_id, validation["error"]])
                        if verbose and validation["error"] == "nonexistent_case":
                            print "Case (%s) from form (%s) does not exist" % (case_id, form_id)
                        elif verbose and validation["error"] == "action_missing":
                            print "Case (%s) missing action for form (%s)" % (case_id, form_id)
                        if rebuild:
                            if verbose:
                                print "rebuilding case (%s) from scratch" % case_id
                            try:
                                rebuild_case(validation["case"] or case_id)
                            except Exception as e:
                                print "Case Rebuild Failure: %s" % e
