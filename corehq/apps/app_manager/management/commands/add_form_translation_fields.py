from corehq.apps.app_manager.management.commands.helpers import AppMigrationCommandBase
from corehq.apps.app_manager.models import Application

from dimagi.utils.chunked import chunked
from corehq.util.log import with_progress_bar


class ResourceNotFound(object):
    pass


class Command(AppMigrationCommandBase):
    help = """
    Populate new 'submit_label' and 'submit_notification_label' in the FormBase class with language translations
    """

    def get_apps(self):
        return Application.objects.all()

    def get_apps_to_migrate(self):
        apps_to_migrate = []
        apps = self.get_apps()
        for app in chunked(with_progress_bar(apps), 100):
            if self._app_need_to_be_migrated(app.build_spec.version):
                apps_to_migrate.append(app)
        return apps_to_migrate

    def _app_need_to_be_migrated(self, app_version):
        major, minor, patch = [int(x) for x in app_version.split('.')]
        return major >= 2 and minor >= 53

    def migrate_form(self, form, translations):
        submit_label_dict = {}
        form_submission_notification_label_dict = {}
        for lang in translations.items():
            submit_label_dict[lang] = "Submit"
            form_submission_notification_label_dict[lang] = "${0} successfully saved!"
        form.submit_label = submit_label_dict
        form.submit_notification_label = form_submission_notification_label_dict

    def migrate(self, app):
        try:
            translations = app.translations
        except (ResourceNotFound, AttributeError):
            return
        modules = list(self.app.get_modules())
        for module in modules:
            for form in module.get_forms():
                self.migrate_form(form, translations)

    def handle(self):
        for app in self.apps_to_migrate():
            self.migrate(app)
