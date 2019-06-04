from __future__ import absolute_import
from __future__ import unicode_literals
from __future__ import print_function

from io import open

from django.core.management.base import BaseCommand

from casexml.apps.case.cleanup import rebuild_case_from_forms
from casexml.apps.case.xform import get_case_updates
from corehq.apps.users.models import CouchUser
from corehq.form_processor.backends.sql.dbaccessors import LedgerAccessorSQL
from corehq.form_processor.interfaces.dbaccessors import FormAccessors
from corehq.form_processor.models import RebuildWithReason
from corehq.util.log import with_progress_bar
from corehq.form_processor.interfaces.processor import FormProcessorInterface
from corehq.form_processor.parsers.ledgers.form import get_case_ids_from_stock_transactions


class Command(BaseCommand):
    help = """
        Bulk archive forms for user on domain.
        First archive all forms and then rebuild corresponding cases
    """

    def add_arguments(self, parser):
        parser.add_argument('user_id')
        parser.add_argument('domain')

    def handle(self, user_id, domain, **options):
        user = CouchUser.get_by_user_id(user_id)
        form_accessor = FormAccessors(domain)

        # ordered with latest form's id on top
        form_ids = form_accessor.get_form_ids_for_user(user_id)
        forms = [f for f in form_accessor.get_forms(form_ids) if f.is_normal]
        print("Found %s normal forms for user" % len(forms))

        case_ids_to_rebuild = set()
        for form in with_progress_bar(forms):
            form_case_ids = set(cu.id for cu in get_case_updates(form))
            if form_case_ids:
                case_ids_to_rebuild.update(form_case_ids)
        case_ids_to_rebuild = list(case_ids_to_rebuild)
        print("Found %s cases that would need to be rebuilt" % len(case_ids_to_rebuild))

        # archive forms
        print("Starting with form archival")
        with open("forms_archived.txt", "w+b") as forms_log:
            for form in with_progress_bar(forms):
                forms_log.write("%s\n" % form.form_id)
                form.archive(rebuild_models=False)

        # removing ledger transactions
        print("Starting with removing ledger transactions")
        with open("ledger_transactions_removed_case_ids.txt", "w+b") as case_ids_log:
            forms_iterated = 0
            for xform in with_progress_bar(forms):
                forms_iterated += 1
                if forms_iterated % 100 == 0:
                    print("traversed %s forms" % forms_iterated)
                ledger_case_ids = get_case_ids_from_stock_transactions(xform)
                if ledger_case_ids:
                    ledger_case_ids = list(ledger_case_ids)
                    for ledger_case_id in ledger_case_ids:
                        case_ids_log.write("%s\n" % ledger_case_id)
                    LedgerAccessorSQL.delete_ledger_transactions_for_form(ledger_case_ids, xform.form_id)

        # rebuild cases
        print("Starting with cases rebuild")
        reason = "User %s forms archived for domain %s by system" % (user.raw_username, domain)
        form_processor_interface = FormProcessorInterface(domain)
        with open("cases_rebuilt.txt", "w+b") as case_log:
            for case_id in with_progress_bar(case_ids_to_rebuild):
                case_log.write("%s\n" % case_id)
                rebuild_case_from_forms(domain, case_id, RebuildWithReason(reason=reason))
                ledgers = form_processor_interface.ledger_db.get_ledgers_for_case(case_id)
                for ledger in ledgers:
                    form_processor_interface.ledger_processor.rebuild_ledger_state(
                        case_id, ledger.section_id, ledger.entry_id)
