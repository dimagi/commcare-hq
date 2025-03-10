import logging
from corehq.apps.app_manager.management.commands.helpers import (
    DomainAppsOperationCommand,
)
from corehq.apps.app_manager.models import Application
from corehq.util.couch import iter_update
from corehq.util.metrics import metrics_counter
from corehq.toggles import APP_DEPENDENCIES
from corehq.apps.es.domains import DomainES

logger = logging.getLogger('app_migration')
logger.setLevel('DEBUG')


class Command(DomainAppsOperationCommand):
    help = """
    This command is used to top up the app dependencies dropout count on Data Dog.
    """

    include_builds = False
    include_linked_apps = True
    include_deleted_apps = False

    DOMAIN_LIST_FILENAME = 'top_up_app_dependencies_dropout_domain.txt'
    DOMAIN_PROGRESS_NUMBER_FILENAME = 'top_up_app_dependencies_dropout_progress.txt'

    def get_domains(self):
        domains_query = (
            DomainES()
            .in_domains(APP_DEPENDENCIES.get_enabled_domains())
            .real_domains().fields(['name'])
        )
        return [domain['name'] for domain in domains_query.run().hits]

    def run(self, domains, domain_list_position):
        for domain in domains:
            app_ids = self.get_app_ids(domain)
            logger.info('Processing {} apps{}'.format(len(app_ids), f" in {domain}" if domain else ""))
            iter_update(
                Application.get_db(), self.check_application, app_ids, verbose=True, chunksize=self.chunk_size,
            )
            domain_list_position = self.increment_progress(domain_list_position)

    def check_application(self, app_doc):
        app_builds = self._get_app_builds(app_doc['domain'], app_doc['_id'])
        if not app_builds:
            return

        if self._has_app_dependencies(app_builds[0]['value']):
            metrics_counter('commcare.app_build.dependencies_added')
            return

        for build_doc in app_builds[1:]:
            if self._has_app_dependencies(build_doc['value']):
                metrics_counter('commcare.app_build.dependencies_removed')
                break
        return None

    def _get_app_builds(self, domain, app_id):
        return Application.get_db().view(
            'app_manager/saved_app',
            startkey=[domain, app_id, {}],
            endkey=[domain, app_id],
            descending=True,
            reduce=False,
            include_docs=True,
        ).all()

    def _has_app_dependencies(self, app_build):
        return app_build.get('profile', {}).get('features', {}).get('dependencies')
