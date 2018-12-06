from __future__ import absolute_import, print_function, unicode_literals

import logging
from io import open

from django.core.management.base import BaseCommand

from casexml.apps.case.xform import get_case_ids_from_form
from corehq.form_processor.backends.couch.dbaccessors import FormAccessorCouch
from corehq.form_processor.backends.sql.dbaccessors import FormAccessorSQL
from corehq.form_processor.change_publishers import publish_form_saved
from corehq.form_processor.exceptions import XFormNotFound
from corehq.form_processor.interfaces.dbaccessors import LedgerAccessors
from corehq.form_processor.interfaces.processor import FormProcessorInterface
from corehq.form_processor.models import FormReprocessRebuild
from corehq.util.log import with_progress_bar

logger = logging.getLogger(__name__)
logger.setLevel('DEBUG')


class Command(BaseCommand):
    help = ('Republish form changes and rebuild cases')

    def add_arguments(self, parser):
        parser.add_argument('form_ids_file')

    def handle(self, form_ids_file, **options):
        cases_rebuilt = 0
        errored_form_ids = set()
        with open(form_ids_file, 'r') as f:
            lines = f.readlines()
            form_ids = [l.strip() for l in lines]

        for form_id in with_progress_bar(form_ids):
            try:
                form = get_form(form_id)
                publish_form_saved(form)
                cases_rebuilt += rebuild_case_changes(form)
            except Exception:
                errored_form_ids.add(form_id)

        logger.info("Rebuilt {} cases from {} forms. {} errors".format(
            cases_rebuilt, len(form_ids), len(errored_form_ids)))

        if errored_form_ids:
            logger.error("errors in forms:\n{}".format("\n".join(errored_form_ids)))
            with open('form_rebuild_errors.txt', 'w+') as f:
                print("\n".join(errored_form_ids), file=f)


def rebuild_case_changes(form, rebuild_reason=None):
    """
    Publishes changes for the form and rebuilds any touched cases.

    """
    domain = form.domain
    case_ids = get_case_ids_from_form(form)
    for case_id in case_ids:
        detail = FormReprocessRebuild(form_id=form.form_id)
        FormProcessorInterface(domain).hard_rebuild_case(case_id, detail)
        if LedgerAccessors(domain).get_ledger_values_for_case(case_id):
            with open('case_ids_with_ledgers.csv', 'a+') as f:
                print("{}, {}".format(domain, case_id), file=f)

    return len(case_ids)


def get_form(form_id):
    try:
        return FormAccessorSQL.get_form(form_id)
    except XFormNotFound:
        pass
    return FormAccessorCouch.get_form(form_id)
