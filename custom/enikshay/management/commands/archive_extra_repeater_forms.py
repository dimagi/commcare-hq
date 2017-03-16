from django.core.management.base import BaseCommand

from casexml.apps.case.xform import get_case_updates
from casexml.apps.case.xml.parser import CaseUpdateAction
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.form_processor.interfaces.processor import FormProcessorInterface
from corehq.util.log import with_progress_bar

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

    def handle(self, log_file, **options):
        to_archive = []
        episode_case_ids = CaseAccessors(domain).get_case_ids_in_domain("episode")
        for episode_case_id in with_progress_bar(episode_case_ids[:100]):
            nikshay_to_archive = []
            dots_99_to_archvie = []
            case_forms = FormProcessorInterface(domain).get_case_forms(episode_case_id)
            _system_forms_count = 0
            for form in case_forms:
                if form.user_id in ("system", "", None) and form.metadata.username == "system":
                    _system_forms_count += 1
                    updates = get_case_updates(form)
                    update_actions = [update.get_update_action() for update in updates if update.id == episode_case_id]
                    for action in update_actions:
                        if isinstance(action, CaseUpdateAction):
                            if set(action.dynamic_properties.keys()) == {"nikshay_registered", "nikshay_error"}:
                                nikshay_to_archive.append(form)
                            elif set(action.dynamic_properties.keys()) == {"dots_99_registered", "dots_99_error"}:
                                dots_99_to_archvie.append(form)


            nikshay_to_archive = nikshay_to_archive[:-1]
            dots_99_to_archvie = dots_99_to_archvie[:-1]

            # print "Found {} system forms for case {}".format(_system_forms_count, episode_case_id)
            # print "Can archive {}".format(len(nikshay_to_archive) + len(dots_99_to_archvie))

            to_archive.extend(nikshay_to_archive)
            to_archive.extend(dots_99_to_archvie)

        print "Will archive {} forms".format(len(to_archive))

        with open(log_file, "w") as f:
            for form in to_archive:
                f.write(form.form_id + "\n")
                if options['commit']:
                    print "archiving!"
                    #form.archive(user_id="remove_duplicate_forms_script")
