"""
A quick and dirty script to dump IDs for forms, visits, and child cases as CSV

Recommended usage:
    $ ./manage.py export_visit_child | gzip > export_visit_child.csv.gz

"""
from django.core.management import BaseCommand

from casexml.apps.case.models import CommCareCase
from couchforms.dbaccessors import iter_form_ids_by_xmlns, get_forms_by_id
from dimagi.utils.chunked import chunked

DOMAIN = "rec"
FORMS_XMLNS = (
    # XMLNS of the seven forms
    "http://openrosa.org/formdesigner/8a439e01cccb27cd0097f309bef1633263c20275",  # Child Treatment
    "http://openrosa.org/formdesigner/796C928A-7451-486B-8346-3316DB3816E4",  # Ordonnance
    # TODO: etc.
)


class Command(BaseCommand):
    help = 'Dump IDs for forms, visits, and child cases as CSV'

    def handle(self, *args, **options):
        main()


def main():
    header = ("form_id", "xmlns", "imci_visit_id", "rec_child_id", "created_at")
    print(",".join(header))
    for xmlns in FORMS_XMLNS:
        form_ids = iter_form_ids_by_xmlns(DOMAIN, xmlns)
        for form_ids_chunk in chunked(form_ids, 500):
            for couch_form in get_forms_by_id(form_ids_chunk):
                row = (
                    get_form_id(couch_form),
                    xmlns,
                    get_imci_visit_id(couch_form),
                    get_rec_child_id(couch_form),
                    get_created_at(couch_form),
                )
                print(",".join(row))


def get_form_id(couch_form):
    return couch_form.form_json["form_id"]


def get_imci_visit_id(couch_form):
    return couch_form.form_json["form"]["case_case_visit"]["case"]["@case_id"]


def get_rec_child_id(couch_form):
    if "case_case_child" in couch_form.form_json["form"]:
        return couch_form.form_json["form"]["case_case_child"]["case"]["@case_id"]
    imci_visit_id = get_imci_visit_id(couch_form)
    imci_visit = CommCareCase.get(imci_visit_id)
    for index in imci_visit.indices:
        if (
            index.identifier == "parent"
            and index.referenced_type == "rec_child"
        ):
            return index.referenced_id


def get_created_at(couch_form):
    return couch_form.form_json["received_on"]
