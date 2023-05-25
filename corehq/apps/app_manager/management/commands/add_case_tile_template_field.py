import logging

from corehq.apps.app_manager.management.commands.helpers import AppMigrationCommandBase
from corehq.apps.app_manager.suite_xml.const import CASE_TILE_TEMPLATE_NAME_PERSON_SIMPLE
from corehq.toggles import CASE_LIST_TILE


logger = logging.getLogger('audit_app_profile_properties')


class Command(AppMigrationCommandBase):
    help = """
    Changes the boolean Detail.use_case_tiles into a string, Detail.case_tile_template, which contains a template
    slug, or is empty if case tiles are not in use.
    """

    include_builds = True
    include_linked_apps = True
    DOMAIN_LIST_FILENAME = 'add_case_tile_template_field.txt'
    DOMAIN_PROGRESS_NUMBER_FILENAME = 'add_case_tile_template_field.txt'
    chunk_size = 25

    def get_domains(self):
        return CASE_LIST_TILE.get_enabled_domains()

    def migrate_app(self, app):
        app_was_changed = False

        def _migrate_detail(detail):
            if detail and (detail.get('use_case_tiles') is not None):
                if detail['use_case_tiles']:
                    detail['case_tile_template'] = CASE_TILE_TEMPLATE_NAME_PERSON_SIMPLE
                del detail['use_case_tiles']
                return True
            return False

        for module in app['modules']:
            detail_pair = module.get('case_details')
            if detail_pair:
                short_detail, long_detail = detail_pair['short'], detail_pair['long']
                app_was_changed = app_was_changed or _migrate_detail(short_detail) or _migrate_detail(long_detail)
        if app_was_changed:
            return app
