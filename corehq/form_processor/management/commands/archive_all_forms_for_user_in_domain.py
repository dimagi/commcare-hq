from __future__ import absolute_import
from __future__ import unicode_literals
from __future__ import print_function

from io import open

from django.core.management.base import BaseCommand

from casexml.apps.case.cleanup import rebuild_case_from_forms
from corehq.apps.users.models import CouchUser
from corehq.form_processor.interfaces.dbaccessors import FormAccessors
from corehq.form_processor.models import RebuildWithReason
from casexml.apps.case.xform import get_case_updates
from corehq.util.log import with_progress_bar
from corehq.form_processor.interfaces.processor import FormProcessorInterface


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
        print("Found %s normal forms for user" % len(form_ids))

        case_ids_to_rebuild = set()
        for form in forms:
            form_case_ids = set(cu.id for cu in get_case_updates(form))
            case_ids_to_rebuild.update(form_case_ids)
        print("Found %s cases that would need to be rebuilt" % len(case_ids_to_rebuild))

        # archive forms
        print("Starting with form archival")
        with open("forms_archived.txt", "w+b") as forms_log:
            for form in with_progress_bar(forms):
                forms_log.write("%s\n" % form.form_id)
                form.archive(skip_rebuild_cases=True)

        # removing data
        for xform in with_progress_bar(forms):
            FormProcessorInterface(xform.domain).ledger_processor.process_form_archived(xform)

        # archive cases
        print("Starting with case archival")
        reason = "User %s forms archived for domain %s by system" % (user.raw_username, domain)
        with open("cases_rebuilt.txt", "w+b") as case_log:
            for case_id in with_progress_bar(case_ids_to_rebuild):
                case_log.write("%s\n" % case_id)
                rebuild_case_from_forms(domain, case_id, RebuildWithReason(reason=reason))
