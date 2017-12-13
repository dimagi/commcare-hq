from __future__ import absolute_import
from __future__ import print_function
from django.core.management.base import BaseCommand

from casexml.apps.case.cleanup import rebuild_case_from_forms
from casexml.apps.case.signals import rebuild_form_cases
from casexml.apps.case.xform import get_case_updates
from casexml.apps.case.xml.parser import CaseUpdateAction
from corehq.form_processor.interfaces.processor import FormProcessorInterface
from corehq.form_processor.models import UserRequestedRebuild
from corehq.util.log import with_progress_bar
from couchforms.signals import xform_archived

domain = "enikshay"


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument('log_file')

        parser.add_argument(
            '--commit',
            action='store_true',
            dest='commit',
            default=False,
            help="Don't do a dry run, but actually archive the forms",
        )

        parser.add_argument(
            '--case_id',
            required=True,
            dest="case_id",
            help="The case whose repeater forms you want to archive",
        )

        parser.add_argument(
            '--case_property_updated',
            dest="case_property",
            help="""A case property that the repeater updated on the case.
            This is so that we don't archive other system forms against this case."""
        )

    def handle(self, log_file, **options):
        to_archive = []
        case_id = options.get('case_id')
        case_forms = FormProcessorInterface(domain).get_case_forms(case_id)
        for form in case_forms:
            if form.user_id in ("system", "", None) and form.metadata.username == "system":
                updates = get_case_updates(form)
                if options.get('case_property') is not None:
                    update_actions = [
                        update.get_update_action() for update in updates
                        if update.id == case_id
                    ]
                    for action in update_actions:
                        if isinstance(action, CaseUpdateAction):
                            if options.get('case_property') in set(action.dynamic_properties.keys()):
                                to_archive.append(form)
                else:
                    to_archive.append(form)

        to_archive.sort(key=lambda f: f.received_on)
        to_archive = to_archive[:-1]

        print("Will archive {} forms".format(len(to_archive)))

        xform_archived.disconnect(rebuild_form_cases)
        with open(log_file, "w") as f:
            for form in with_progress_bar(to_archive):
                f.write(form.form_id + "\n")
                f.flush()
                if options['commit']:
                    form.archive(user_id="archive_single_case_repeater_forms_script")
        xform_archived.connect(rebuild_form_cases)

        rebuild_case_from_forms(domain, case_id, UserRequestedRebuild(
            user_id="archive_single_case_repeater_forms_script")
        )
