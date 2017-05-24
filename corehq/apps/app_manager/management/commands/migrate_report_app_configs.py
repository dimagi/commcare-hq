import logging
import re
from django.core.management import BaseCommand

from corehq.apps.app_manager.dbaccessors import get_apps_in_domain
from corehq.apps.userreports.exceptions import ReportConfigurationNotFoundError
from toggle.models import Toggle


logger = logging.getLogger('report_module_migration')
logger.setLevel('DEBUG')


class Command(BaseCommand):
    help = '''
        Migrate ReportAppConfig objects from storing graph configurations
        using ReportGraphConfig to storing them using GraphConfiguration
    '''

    def handle(self, **options):
        domains = Toggle.get('mobile_ucr').enabled_users
        domains = [re.sub(r'^domain:', '', d) for d in domains]
        for domain in domains:
            apps = get_apps_in_domain(domain, include_remote=False)
            for app in apps:
                dirty = False
                for module in app.modules:
                    if module.doc_type == 'ReportModule':
                        for config in module.report_configs:
                            if len(config.complete_graph_configs):
                                logger.info("Already migrated module {} in app {} in domain {}".format(
                                    module.id, app.id, domain
                                ))
                            elif len(config.graph_configs):
                                logger.info("Migrating module {} in app {} in domain {}".format(
                                    module.id, app.id, domain
                                ))
                                try:
                                    config.migrate_graph_configs(domain)
                                    dirty = True
                                except ReportConfigurationNotFoundError:
                                    pass
                if dirty:
                    app.save()
        logger.info('Done with migrate_report_app_configs')
