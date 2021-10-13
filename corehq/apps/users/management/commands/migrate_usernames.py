import csv
import logging

from django.core.management import BaseCommand

from toggle.shortcuts import set_toggle

from corehq.apps.ota.models import DeviceLogRequest, MobileRecoveryMeasure
from corehq.apps.users.models import CouchUser, DomainRequest, Invitation
from corehq.apps.users.util import raw_username
from corehq.toggles import NAMESPACE_USER, toggles_enabled_for_user

logger = logging.getLogger(__name__)

CURRENT_USERNAME = 'current_username'
NEW_USERNAME = 'new_username'


class Command(BaseCommand):
    help = "Update a user's username and email"

    def add_arguments(self, parser):
        parser.add_argument('file', help='')
        parser.add_argument('--verbose', action="store_true")

    def handle(self, file, **options):
        logger.setLevel(logging.INFO if options["verbose"] else logging.WARNING)

        for current_username, new_username in self.iterate_usernames_to_update(file):
            logger.info(f'Migrating {current_username} to {new_username}')

            # update Django user, and Couch user
            couch_user = CouchUser.get_by_username(current_username)
            should_update_email = couch_user.username == couch_user.email
            logger.info(f'Updated couch username from {couch_user.username} to {new_username}')
            django_user = couch_user.get_django_user()
            django_user.username = new_username
            django_user.save()
            couch_user.username = new_username
            if should_update_email:
                logger.info(f'Updated couch email from {couch_user.email} to {new_username}')
                couch_user.email = new_username
            else:
                logger.info(f'Only migrating username, not email, for user {couch_user.username}.')
            couch_user.save()
            # clear cache
            CouchUser.get_by_username.clear(CouchUser, current_username)

            self.update_dependent_db_models(current_username, new_username, should_update_email)

            self.update_feature_flags(current_username, new_username)

    def update_dependent_db_models(self, current_username, new_username, should_update_email):
        device_log_requests = DeviceLogRequest.objects.filter(username=raw_username(current_username))
        if device_log_requests:
            for log_request in device_log_requests:
                new_raw_username = raw_username(new_username)
                logger.info(f'Updating DeviceLogRequest from {log_request.username} to {new_raw_username}')
                log_request.username = new_raw_username
                log_request.save()

        domain_requests = DomainRequest.objects.filter(email=current_username)
        if domain_requests and should_update_email:
            for domain_request in domain_requests:
                logger.info(f'Updating DomainRequest from {domain_request.email} to {new_username}')
                domain_request.email = new_username
                domain_request.save()

        pending_invitations = Invitation.objects.filter(email=current_username, is_accepted=False)
        if pending_invitations and should_update_email:
            for invitation in pending_invitations:
                logger.info(f'Updating Invitation from {invitation.email} to {new_username}')
                invitation.email = new_username
                invitation.save()

        recovery_measures = MobileRecoveryMeasure.objects.filter(username=current_username)
        if recovery_measures:
            for recovery_measure in recovery_measures:
                logger.info(
                    f'Updating MobileRecoveryMeasure from {recovery_measure.username} to {new_username}'
                )
                recovery_measure.username = new_username
                recovery_measure.save()

    def update_feature_flags(self, current_username, new_username):
        enabled_toggles = toggles_enabled_for_user(current_username)
        for toggle in enabled_toggles:
            set_toggle(toggle, current_username, False, namespace=NAMESPACE_USER)
            set_toggle(toggle, new_username, True, namespace=NAMESPACE_USER)

    def iterate_usernames_to_update(self, file):
        with open(file, newline='') as csvfile:
            spamreader = csv.reader(csvfile, delimiter=' ', quotechar='|')
            header = next(spamreader)
            header_values = header[0].split(',')
            try:
                current_user_index = header_values.index(CURRENT_USERNAME)
                new_user_index = header_values.index(NEW_USERNAME)
            except ValueError:
                logger.error(f'The provided csv file should contain both a {CURRENT_USERNAME} and {NEW_USERNAME} '
                             'header column')
                return
            for row in spamreader:
                row_values = row[0].split(',')
                yield row_values[current_user_index], row_values[new_user_index]
