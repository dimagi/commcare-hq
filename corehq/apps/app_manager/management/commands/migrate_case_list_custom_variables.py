from corehq.apps.app_manager.management.commands.helpers import AppMigrationCommandBase
from corehq.toggles import CASE_LIST_CUSTOM_VARIABLES

from lxml import etree


class Command(AppMigrationCommandBase):
    help = """Migrate case list custom variables from xml to dict and back"""

    include_builds = True
    include_linked_apps = True
    DOMAIN_LIST_FILENAME = 'migrate_case_list_custom_variables_domain.txt'
    DOMAIN_PROGRESS_NUMBER_FILENAME = 'migrate_case_list_custom_variables_progress.txt'
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
        return CASE_LIST_CUSTOM_VARIABLES.get_enabled_domains()

    @staticmethod
    def parse(xml):
        elems = etree.fromstring(f"<w>{xml}</w>")
        return {e.tag: e.get("function") for e in elems}

    @staticmethod
    def migrate_detail_forward(detail):
        if detail and (detail.get('custom_variables') is not None) and \
                (detail.get('custom_variables_dict') is None):
            detail['custom_variables_dict'] = Command.parse(detail['custom_variables'])
            return True
        return False

    @staticmethod
    def migrate_detail_backward(detail):
        if detail and detail.get('custom_variables_dict') is not None:
            del detail['custom_variables_dict']
            return True
        return False

    @staticmethod
    def migrate_app_impl(app, reverse):
        app_was_changed = False

        migrate_detail = Command.migrate_detail_forward
        if reverse:
            migrate_detail = Command.migrate_detail_backward

        for module in app['modules']:
            detail_pair = module.get('case_details')
            if detail_pair:
                short_detail, long_detail = detail_pair['short'], detail_pair['long']
                app_was_changed_short = migrate_detail(short_detail)
                app_was_changed_long = migrate_detail(long_detail)
                app_was_changed = app_was_changed or app_was_changed_short or app_was_changed_long
        if app_was_changed:
            return app

    def migrate_app(self, app):
        reverse = self.options['reverse']
        return Command.migrate_app_impl(app, reverse)
