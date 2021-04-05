import logging

from django.core.management.base import BaseCommand

from corehq.apps.app_manager.dbaccessors import get_all_built_app_ids_and_versions, get_app, wrap_app
from corehq.apps.app_manager.exceptions import ResourceOverrideError
from corehq.apps.app_manager.models import LinkedApplication
from corehq.apps.app_manager.suite_xml.post_process.resources import (
    add_xform_resource_overrides,
    get_xform_resource_overrides,
)
from corehq.apps.linked_domain.applications import get_master_app_by_version
from corehq.apps.linked_domain.exceptions import ActionNotPermitted
from corehq.dbaccessors.couchapps.all_docs import (
    get_deleted_doc_ids_by_class,
    get_doc_ids_by_class,
)
from corehq.util.couch import iter_update
from corehq.util.log import with_progress_bar

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    dry_run = False
    help = """
        Adds ResourceOverride objects for either a given linked app or all linked apps across all domains.
    """

    def _add_overrides_for_build(self, doc):
        linked_build = wrap_app(doc)
        log_prefix = "{}{} app {}, build {}".format("[DRY RUN] " if self.dry_run else "",
                                                    linked_build.domain,
                                                    linked_build.origin_id,
                                                    linked_build.get_id)

        if not linked_build.upstream_app_id or not linked_build.upstream_version:
            return

        if not linked_build.domain_link:
            logger.error("{}: Skipping due to missing domain link".format(log_prefix))
            return

        try:
            master_build = get_master_app_by_version(linked_build.domain_link, linked_build.upstream_app_id,
                                                     linked_build.upstream_version)
        except ActionNotPermitted:
            logger.error("{}: Skipping due to 403".format(log_prefix))
            return

        if not master_build:
            logger.info("{}: Skipping, no master build found".format(log_prefix))
            return

        linked_map = self._get_xmlns_map(linked_build)
        master_map = self._get_xmlns_map(master_build)
        override_map = {
            master_form_unique_id: linked_map[xmlns]
            for xmlns, master_form_unique_id in master_map.items() if xmlns in linked_map
        }

        if not override_map:
            logger.info("{}: Skipping, no forms found to map".format(log_prefix))
            return

        current_overrides = {
            pre_id: override.post_id
            for pre_id, override
            in get_xform_resource_overrides(linked_build.domain, linked_build.origin_id).items()
        }
        if set(override_map.items()) - set(current_overrides.items()):
            logger.info("{}: Found {} overrides, updating with {}".format(log_prefix,
                                                                          len(current_overrides),
                                                                          len(override_map)))
            if not self.dry_run:
                try:
                    add_xform_resource_overrides(linked_build.domain, linked_build.origin_id, override_map)
                except ResourceOverrideError as e:
                    logger.error("{}".format(str(e)))   # skip log_prefix, error message has same info
        else:
            logger.info("{}: Skipping, all {} overrides already present".format(log_prefix, len(override_map)))

    def _get_xmlns_map(self, app):
        return {
            f.xmlns: f.unique_id
            for m in app.get_modules() for f in app.get_forms() if f.form_type != 'shadow_form'
        }

    def add_arguments(self, parser):
        parser.add_argument(
            '--domain',
            help='Required if passing app id.',
        )
        parser.add_argument(
            '--app-id',
            help='If provided, handle only this app.',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            default=False,
            help='Do not actually modify the database, just log what will happen',
        )
        parser.add_argument(
            '--ignore-deleted',
            action='store_true',
            default=False,
            help='Skip deleted apps',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            default=False,
            help='Log every action, including apps that were skipped',
        )

    def handle(self, domain=None, app_id=None, dry_run=False, ignore_deleted=False, verbose=False, **options):
        self.dry_run = dry_run
        if verbose:
            logger.setLevel(logging.DEBUG)
        else:
            logger.setLevel(logging.ERROR)

        if domain and app_id:
            app = get_app(domain, app_id)   # Sanity check, will 404 if domain doesn't match
            assert(app.doc_type == 'LinkedApplication' or app.doc_type == 'LinkedApplication-Deleted')
            app_ids = set([v.build_id for v in get_all_built_app_ids_and_versions(domain, app_id)])
            app_ids.add(app_id)  # in case linked app has no builds yet
        else:
            app_ids = get_doc_ids_by_class(LinkedApplication)
            if not ignore_deleted:
                app_ids += get_deleted_doc_ids_by_class(LinkedApplication)
        iter_update(LinkedApplication.get_db(),
                    self._add_overrides_for_build,
                    with_progress_bar(app_ids),
                    chunksize=1)
