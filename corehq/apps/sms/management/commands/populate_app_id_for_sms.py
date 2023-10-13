import logging

from django.core.management.base import BaseCommand

from corehq.apps.app_manager.util import get_app_id_from_form_unique_id
from corehq.apps.sms.models import Keyword, KeywordAction, MessagingEvent, MessagingSubEvent

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = """
        Populate any KeywordAction, MessagingEvent, and MessagingSubEvent models
        that contain a form_unique_id with the associated app_id.
    """

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            default=False,
            help='Do not actually modify the database, just verbosely log what will happen',
        )

    def handle(self, dry_run=False, **options):
        def _update_objects(model, domain, form_unique_id):
            log_prefix = "{} Domain {}, {}, form unique_id {}".format("[DRY RUN]" if dry_run else "",
                                                                      model.__name__,
                                                                      domain,
                                                                      form_unique_id)
            app_id = get_app_id_from_form_unique_id(domain, form_unique_id)
            if app_id:
                to_update = model.objects.filter(form_unique_id=action.form_unique_id, app_id__isnull=True)
                if not dry_run:
                    to_update.update(app_id=app_id)
                logger.info("{}: Updated {} models to use app id {}".format(log_prefix, to_update.count(), app_id))
            else:
                logger.info("{}: Could not find app".format(log_prefix))

        for domain_keyword in Keyword.objects.distinct('domain'):
            for keyword in Keyword.objects.filter(domain=domain_keyword.domain):
                for action in keyword.keywordaction_set.filter(form_unique_id__isnull=False, app_id__isnull=True):
                    _update_objects(KeywordAction, keyword.domain, action.form_unique_id)

        events = MessagingEvent.objects.filter(form_unique_id__isnull=False, app_id__isnull=True)
        for event in events.distinct('domain', 'form_unique_id'):
            _update_objects(MessagingEvent, event.domain, event.form_unique_id)

        subevents = MessagingSubEvent.objects.filter(form_unique_id__isnull=False, app_id__isnull=True)
        for subevent in subevents.distinct('domain', 'form_unique_id'):
            _update_objects(MessagingSubEvent, subevent.parent.domain, subevent.form_unique_id)
