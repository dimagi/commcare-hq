import re
from corehq.apps.app_manager.management.commands.helpers import AppMigrationCommandBase
from corehq.apps.app_manager.models import Application, load_app_template, ATTACHMENT_REGEX
from corehq.apps.app_manager.util import update_unique_ids
from corehq.apps.es import AppES


def _get_first_form_id(app):
    return app['modules'][0]['forms'][0]['unique_id']


class Command(AppMigrationCommandBase):
    help = "Migrate apps that have been created from template apps " \
           "to make sure that their form ID's are unique."

    include_builds = False

    def migrate_app(self, app_doc):
        should_save = False

        template_slug = app_doc['created_from_template']
        template = load_app_template(template_slug)

        if _get_first_form_id(app_doc) == _get_first_form_id(template):
            should_save = True
            app = Application.wrap(app_doc)

            _attachments = {}
            for name in app_doc.get('_attachments', {}):
                if re.match(ATTACHMENT_REGEX, name):
                    _attachments[name] = app.fetch_attachment(name)
            app_doc['_attachments'] = _attachments

            app_doc = update_unique_ids(app_doc)

        return Application.wrap(app_doc) if should_save else None

    def get_app_ids(self):
        q = AppES().created_from_template(True).is_build(False).fields('_id')
        results = q.run()
        return [app['_id'] for app in results.hits]

