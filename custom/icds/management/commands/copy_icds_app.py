
from django.core.management import BaseCommand

from corehq.apps.app_manager.dbaccessors import get_build_doc_by_version, wrap_app
from corehq.apps.app_manager.models import import_app
from corehq.util.view_utils import absolute_reverse


class Command(BaseCommand):
    help = "Make a copy of a specific version of an application on the same domain"

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('app_id')
        parser.add_argument('version')
        parser.add_argument('new_name')

    def handle(self, domain, app_id, version, new_name, **options):
        old_app = get_app_by_version(domain, app_id, version)
        new_app = import_app(old_app.to_json(), domain, source_properties={'name': new_name})

        old_to_new = get_old_to_new_config_ids(old_app, new_app)
        for form in new_app.get_forms():
            for old_id, new_id in old_to_new:
                form.source = form.source.replace(old_id, new_id)

        new_app.save()
        print("App succesfully copied, you can view it at\n{}".format(
            absolute_reverse('view_app', args=[domain, new_app.get_id])
        ))


def get_app_by_version(domain, app_id, version):
    app = get_build_doc_by_version(domain, app_id, version)
    if not app:
        raise Exception("No app found with id '{}' and version '{}', on '{}'"
                        .format(app_id, version, domain))
    return wrap_app(app)


def get_old_to_new_config_ids(old_app, new_app):
    return [
        (old_config.uuid, new_config.uuid)
        for old_module, new_module in zip(old_app.get_report_modules(), new_app.get_report_modules())
        for old_config, new_config in zip(old_module.report_configs, new_module.report_configs)
    ]
