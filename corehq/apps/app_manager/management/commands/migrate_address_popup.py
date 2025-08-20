from corehq.apps.app_manager.management.commands.helpers import AppMigrationCommandBase
from corehq.toggles import CASE_LIST_MAP


class Command(AppMigrationCommandBase):
    help = """Migrate case list address popup fields to case detail"""

    include_builds = True
    include_linked_apps = True
    DOMAIN_LIST_FILENAME = 'migrate_address_popup_domain.txt'
    DOMAIN_PROGRESS_NUMBER_FILENAME = 'migrate_address_popup_progress.txt'
    chunk_size = 1

    def add_arguments(self, parser):
        super(Command, self).add_arguments(parser)

        parser.add_argument(
            '--reverse',
            action='store_true',
            default=False,
            help="Perform the migration in reverse",
        )

    def get_domains(self):
        return CASE_LIST_MAP.get_enabled_domains()

    @staticmethod
    def migrate_app_impl(app, reverse):
        app_was_changed = False

        for module in app['modules']:
            detail_pair = module.get('case_details')
            if detail_pair:
                if reverse:
                    detail_from, detail_to = detail_pair['long'], detail_pair['short']
                else:
                    detail_from, detail_to = detail_pair['short'], detail_pair['long']

                address_popup_columns = \
                    [c for c in detail_from.get('columns') if c.get('format') == 'address-popup']
                if len(address_popup_columns) > 0:
                    app_was_changed = app_was_changed or True
                    other_columns = [c for c in detail_from.get('columns') if c.get('format') != 'address-popup']

                    detail_from['columns'] = other_columns
                    detail_to_columns = detail_to.get('columns', [])
                    detail_to_columns.extend(address_popup_columns)
                    detail_to['columns'] = detail_to_columns

        if app_was_changed:
            return app

    def migrate_app(self, app):
        reverse = self.options['reverse']
        return Command.migrate_app_impl(app, reverse)
