from corehq.apps.app_manager.management.commands.helpers import AppMigrationCommandBase
from corehq.apps.app_manager.models import Application


class Command(AppMigrationCommandBase):
    help = "Migrate Forms and Modules to have icon/audio as a dict " \
           "so that they can be localized to multiple languages"

    should_save = False

    def migrate_app(self, app_doc):
        new_modules = []
        for module in app_doc['modules']:
            module = self.wrap_media(module)
            if 'case_list_form' in module:
                module['case_list_form'] = self.wrap_media(module['case_list_form'])

            new_forms = []
            for form in module['forms']:
                new_forms.append(self.wrap_media(form))
            module['forms'] = new_forms
            new_modules.append(module)
        app_doc['modules'] = new_modules

        return Application.wrap(app_doc) if self.should_save else None

    def wrap_media(self, doc):
        for media_attr in ('media_image', 'media_audio'):
            old_media = doc.get(media_attr, None)
            if old_media and isinstance(old_media, basestring):
                doc[media_attr] = {'default': old_media}
                self.should_save = True
        return doc
