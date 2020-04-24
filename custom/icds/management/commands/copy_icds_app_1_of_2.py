from django.core.management import BaseCommand, CommandError

from corehq.apps.app_manager.dbaccessors import get_build_doc_by_version, wrap_app
from corehq.apps.app_manager.models import import_app
from corehq.util.view_utils import absolute_reverse


class Command(BaseCommand):
    help = """
        For use when creating a new master app for ICDS.

        Makes a copy of a specific version of an application using the normal
        copy app workflow and then does a find and replace on report UUIDs in
        all form XML.

        This command is necessary until the ICDS apps are migrated to UCR v2.
    """

    def add_arguments(self, parser):
        parser.add_argument('app_id')
        parser.add_argument('version')
        parser.add_argument('source_domain')
        parser.add_argument('target_domain')
        parser.add_argument('new_name')
        parser.add_argument('--skip-dynamic-report-check', action='store_true', default=False)

    def handle(self, app_id, version, source_domain, target_domain, new_name, **options):
        if options['skip_dynamic_report_check']:
            message = """
                WARNING: You are skipping report-related safety checks.
                If your app uses mobile UCR and contains references to dynamic reports, it will break
                if those references do not use aliases to reference the correct report ids.
                Do you wish to proceed?
            """
            response = input('{} [y/N]'.format(message)).lower()
            if response != 'y':
                raise CommandError('abort')

        old_app = get_app_by_version(source_domain, app_id, version)
        new_app = import_app(old_app.to_json(), target_domain, source_properties={'name': new_name},
                             check_all_reports=not(options['skip_dynamic_report_check']))

        find_and_replace_report_ids(old_app, new_app)

        new_app.save()

        print("App succesfully copied, you can view it at\n{}".format(
            absolute_reverse('view_app', args=[target_domain, new_app.get_id])
        ))

        print("""
            Next, make a build of the new app and then run copy_icds_app_2_of_2
            for all linked apps that use this app as a master app.
        """)


def get_app_by_version(domain, app_id, version):
    app = get_build_doc_by_version(domain, app_id, version)
    if not app:
        raise Exception("No app found with id '{}' and version '{}', on '{}'"
                        .format(app_id, version, domain))
    return wrap_app(app)


def find_and_replace_report_ids(old_app, new_app):
    old_to_new = get_old_to_new_config_ids(old_app, new_app)
    for form in new_app.get_forms():
        if form.form_type != 'shadow_form':
            for old_id, new_id in old_to_new:
                form.source = form.source.replace(old_id, new_id)


def get_old_to_new_config_ids(old_app, new_app):
    return [
        (old_config.uuid, new_config.uuid)
        for old_module, new_module in zip(old_app.get_report_modules(), new_app.get_report_modules())
        for old_config, new_config in zip(old_module.report_configs, new_module.report_configs)
    ]
