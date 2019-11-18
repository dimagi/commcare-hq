import logging
from itertools import chain

from django.core.management.base import BaseCommand

from corehq.apps.app_manager.util import get_app_id_from_form_unique_id
from corehq.messaging.scheduling.models import AlertSchedule, TimedSchedule

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = """
        Populate any SMSSurveyContent and IVRSurveyContent models that
        contain a form_unique_id with the associated app_id.
    """

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            default=False,
            help='Do not actually modify the database, just verbosely log what will happen',
        )

    def handle(self, dry_run=False, **options):
        def _update_model(model, domain):
            if model.form_unique_id is None or model.app_id is not None:
                return None

            log_prefix = "{} Domain {}, form unique_id {}".format("[DRY RUN]" if dry_run else "",
                                                                  domain,
                                                                  model.form_unique_id)
            model.app_id = get_app_id_from_form_unique_id(domain, model.form_unique_id)
            if model.app_id:
                if not dry_run:
                    model.save()
                logger.info("{}: Updated {} to use app id {}".format(log_prefix,
                                                                     model.__class__.__name__,
                                                                     model.app_id))
            else:
                logger.info("{}: Could not find app".format(log_prefix))

        for schedule in chain(AlertSchedule.objects.all(), TimedSchedule.objects.all()):
            for event in schedule.memoized_events:
                if event.sms_survey_content:
                    _update_model(event.sms_survey_content, schedule.domain)
                if event.ivr_survey_content:
                    _update_model(event.ivr_survey_content, schedule.domain)
