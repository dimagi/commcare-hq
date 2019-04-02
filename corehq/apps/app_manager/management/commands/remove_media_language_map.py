from __future__ import absolute_import
from __future__ import unicode_literals
from corehq.apps.app_manager.management.commands.helpers import AppMigrationCommandBase
from corehq.apps.app_manager.models import Application


class Command(AppMigrationCommandBase):
    help = "One-time migration to remove the media_language_map attribute from all applications"

    include_builds = True

    def add_arguments(self, parser):
        super(Command, self).add_arguments(parser)
        parser.add_argument(
            '--overwrite_empties',
            action='store_true',
            dest='overwrite_empties',
            default=False,
            help="Update any app with the attribute, even if it's an empty dict",
        )

    def migrate_app(self, app_doc):
        should_save = False
        if 'media_language_map' in app_doc:
            data = app_doc.pop('media_language_map')
            should_save = data or self.options['overwrite_empties']
        return Application.wrap(app_doc) if should_save else None
