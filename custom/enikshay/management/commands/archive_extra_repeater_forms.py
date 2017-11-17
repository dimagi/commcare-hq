from __future__ import absolute_import
from __future__ import print_function
from django.core.management.base import BaseCommand

from casexml.apps.case.cleanup import rebuild_case_from_forms
from casexml.apps.case.signals import rebuild_form_cases
from casexml.apps.case.xform import get_case_updates
from casexml.apps.case.xml.parser import CaseUpdateAction
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
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
            '--limit',
            dest='limit',
            type=int,
            help="Limit to the first n cases",
        )

    def handle(self, log_file, **options):
        to_archive = []
        cases_affected = set()
        episode_case_ids = CaseAccessors(domain).get_case_ids_in_domain("episode")
        if options.get('limit'):
            episode_case_ids = episode_case_ids[:options.get('limit')]
        for episode_case_id in with_progress_bar(episode_case_ids):
            nikshay_to_archive = []
            dots_99_to_archvie = []
            case_forms = FormProcessorInterface(domain).get_case_forms(episode_case_id)
            for form in case_forms:
                if form.user_id in ("system", "", None) and form.metadata.username == "system":
                    updates = get_case_updates(form)
                    update_actions = [
                        update.get_update_action() for update in updates
                        if update.id == episode_case_id
                    ]
                    for action in update_actions:
                        if isinstance(action, CaseUpdateAction):
                            if set(action.dynamic_properties.keys()) == {"nikshay_registered", "nikshay_error"}:
                                nikshay_to_archive.append(form)
                                cases_affected.add(episode_case_id)
                            elif set(action.dynamic_properties.keys()) == {"dots_99_registered", "dots_99_error"}:
                                cases_affected.add(episode_case_id)
                                dots_99_to_archvie.append(form)

            # get_case_updates() returns the forms in the correct order, but sorting is probably a good idea in case
            # get_case_updates ever changes.
            nikshay_to_archive.sort(key=lambda f: f.received_on)
            dots_99_to_archvie.sort(key=lambda f: f.received_on)
            nikshay_to_archive = nikshay_to_archive[:-1]
            dots_99_to_archvie = dots_99_to_archvie[:-1]

            to_archive.extend(nikshay_to_archive)
            to_archive.extend(dots_99_to_archvie)

        print("Will archive {} forms".format(len(to_archive)))

        xform_archived.disconnect(rebuild_form_cases)
        with open(log_file, "w") as f:
            for form in with_progress_bar(to_archive):
                f.write(form.form_id + "\n")
                f.flush()
                if options['commit']:
                    form.archive(user_id="remove_duplicate_forms_script")
        xform_archived.connect(rebuild_form_cases)

        print("Will rebuild {} cases".format(len(cases_affected)))
        for case_id in with_progress_bar(cases_affected):
            rebuild_case_from_forms(domain, case_id, UserRequestedRebuild(user_id="remove_duplicate_forms_script"))
