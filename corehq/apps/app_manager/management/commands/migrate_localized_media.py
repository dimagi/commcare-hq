from __future__ import absolute_import
from __future__ import unicode_literals
from corehq.apps.app_manager.management.commands.helpers import AppMigrationCommandBase
from corehq.apps.app_manager.models import Application
from corehq.util.python_compatibility import soft_assert_type_text
import six


class Command(AppMigrationCommandBase):
    help = "Migrate Forms and Modules to have icon/audio as a dict " \
           "so that they can be localized to multiple languages. "\
           "To reverse migrate use the option --backwards."
    # Caution: backwards is not reversible, as some of multi-lang media references will be lost

    include_builds = True

    def add_arguments(self, parser):
        super(Command, self).add_arguments(parser)
        parser.add_argument(
            '--backwards',
            action='store_true',
            dest='backwards',
            default=False,
            help='Reverse this migration',
        )

    def migrate_app(self, app_doc):
        new_modules = []
        should_save = False
        if not self.options['backwards']:
            migrate_fn = self._localize_doc
        else:
            migrate_fn = self._reverse_localize_doc

        for module in app_doc['modules']:
            # update module media
            module, _should_save = migrate_fn(module)
            should_save = should_save or _should_save

            nav_menu_media_attrs = [
                'case_list',
                'task_list',
                'referral_list',
                'case_list_form',
            ]
            # update other module menu media
            for attr in nav_menu_media_attrs:
                if attr in module:
                    update, _should_save = migrate_fn(module[attr])
                    should_save = should_save or _should_save
                    module[attr] = update

            # update form media
            new_forms = []
            for form in module['forms']:
                update, _should_save = migrate_fn(form)
                should_save = should_save or _should_save
                new_forms.append(update)

            module['forms'] = new_forms
            new_modules.append(module)
        app_doc['modules'] = new_modules

        return Application.wrap(app_doc) if should_save else False

    @staticmethod
    def _localize_doc(doc):
        should_save = False
        for media_attr in ('media_image', 'media_audio'):
            old_media = doc.get(media_attr, None)
            if old_media and isinstance(old_media, six.string_types):
                soft_assert_type_text(old_media)
                doc[media_attr] = {'default': old_media}
                should_save = True

        return doc, should_save

    @staticmethod
    def _reverse_localize_doc(doc):
        should_save = False
        for media_attr in ('media_image', 'media_audio'):
            old_media = doc.get(media_attr, None)
            if old_media is not None and isinstance(old_media, dict):
                # media set by localized-migration
                new_media = old_media.get('default')
                if old_media and not new_media:
                    # media set by user on localized branch
                    new_media = sorted(old_media.items())[0][1]
                    # non-localized media doesn't accept empty paths
                    if new_media == '':
                        new_media = None
                doc[media_attr] = new_media
                should_save = True

        return doc, should_save
