import logging

from django.core.management.base import BaseCommand

from corehq.apps.app_manager.util import get_app_id_from_form_unique_id
from corehq.apps.ivr.models import Call

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Populate any Call models that contain a form_unique_id with the associated app_id."

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            default=False,
            help='Do not actually modify the database, just verbosely log what will happen',
        )

    def handle(self, dry_run=False, **options):
        for call in Call.objects.distinct('domain', 'form_unique_id').filter(app_id__isnull=True,
                                                                             form_unique_id__isnull=False):
            log_prefix = "{} Domain {}, form unique_id {}".format("[DRY RUN]" if dry_run else "",
                                                                  call.domain,
                                                                  call.form_unique_id)
            app_id = get_app_id_from_form_unique_id(call.domain, call.form_unique_id)
            if app_id:
                to_update = Call.objects.filter(form_unique_id=call.form_unique_id)
                if not dry_run:
                    to_update.update(app_id=app_id)
                logger.info("{}: Updated {} calls to use app id {}".format(log_prefix, to_update.count(), app_id))
            else:
                logger.info("{}: Could not find app".format(log_prefix))
