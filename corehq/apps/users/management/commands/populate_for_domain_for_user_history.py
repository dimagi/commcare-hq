import logging
import re

from django.core.management.base import BaseCommand

from memoized import memoized

from corehq.apps.user_importer.models import UserUploadRecord
from corehq.apps.users.audit.change_messages import REMOVE_FROM_DOMAIN
from corehq.apps.users.models import CommCareUser, UserHistory, WebUser
from corehq.const import USER_CHANGE_VIA_API

DOMAIN_REMOVE_REGEX = re.compile(r"Removed from domain '(\S+)'")


class Command(BaseCommand):
    help = "Populate missing values for for_domain column for User History records"

    def add_arguments(self, parser):
        parser.add_argument(
            '--save',
            action='store_true',
            dest='save',
            default=False,
            help="actually update records else just log",
        )

    def handle(self, **options):
        """
        for any log which has user_type == 'CommCareUser'
          for_domain == user.domain

        for web user
            if action == UserModelAction.CREATE.value or UserModelAction.DELETE.value
                skip
            else
                For logs with bulk_upload_record_id:
                    find the user row in results and use the 'domain' column as for_domain if available
                    or else same as by_domain in the log

                find for domain from domain removal message for
                1. for any log that has domain removal message

                Not needed for
                1. changed_via == corehq.apps.domain.management.commands.make_superuser (by_domain: None)
                2. Changes by django admin views (corehq/apps/hqadmin/views/users.py) (by_domain: None)
                3. Account level changes by users (corehq/apps/settings/views.py) (by_domain: None)

                For rest
                same as by_domain if available
                1. updates via user forms
        """
        update_records = options['save']
        if update_records:
            confirmation = input("Confirming that you want to update records as well (y)")
            if confirmation != 'y':
                logging.info("Exiting")
                exit()

        failed_bulk_upload_hit = []
        unexpected_flag_value = {}
        succeeded = {}

        with open("populate_for_domain_for_user_history.txt", 'w') as _file:
            for user_history in UserHistory.objects.order_by('pk').iterator():
                for_domain = None
                by_domain = user_history.by_domain
                if user_history.user_type == "CommCareUser":
                    for_domain = _get_commcare_users_domain(user_history.user_id)
                    if not for_domain:
                        logging.warning(
                            f"Could not get domain for log {user_history.pk} for user {user_history.user_id}")
                        _file.write(
                            f"{user_history.pk}, {user_history.user_type}, {user_history.user_id}, {by_domain}, 'N/A', {user_history.change_messages}, {user_history.user_upload_record_id}\n"
                        )

                elif user_history.user_type == "WebUser":
                    if user_history.action in [UserHistory.CREATE, UserHistory.DELETE]:
                        continue
                    # stay flexible with new changed_via or old message details for dry runs
                    if hasattr(user_history, 'changed_via'):
                        changed_via = user_history.changed_via
                    else:
                        changed_via = user_history.details['changed_via']
                    # an api change
                    if changed_via == USER_CHANGE_VIA_API:
                        continue
                    if user_history.action != UserHistory.UPDATE:
                        raise Exception(f"Unexpected action value set {user_history.action}")

                    # find for_domain for a bulk upload
                    if user_history.user_upload_record_id:
                        upload_record = _get_user_bulk_upload_record(user_history.user_upload_record_id)
                        if not upload_record:
                            raise Exception(f"Missing bulk upload record {user_history.user_upload_record_id}")
                        result = upload_record.result
                        if result is None:
                            failed_bulk_upload_hit.append(upload_record.pk)
                            continue
                        user_record = None
                        # results is a list of "rows"
                        # each entry is a dict with keys 'username', 'flag', 'row'
                        # a 'row' is the excel row in the upload where column 'web_user' is the web user's username
                        # a 'flag' is updated/created or the exception but if a log was created it should be
                        # updated/created
                        username = _get_web_users_username_by_id(user_history.user_id)
                        if not username:
                            raise Exception(f"Could not get username for web user {user_history.user_id}")
                        for row in result['rows']:
                            # a web user change via mobile user bulk upload
                            if 'web_user' in row['row']:
                                if row['row']['web_user'] == username:
                                    user_record = row
                                    break
                            # a web user bulk upload
                            elif row['username'] == username:
                                user_record = row
                                break
                        if not user_record:
                            raise Exception(
                                f"Missing user {username} record in {user_history.user_upload_record_id}")
                        if user_record['flag'] in ['created', 'updated']:
                            for_domain = user_record['row'].get('domain') or upload_record.domain
                        else:
                            # raise Exception(f"Unexpected flag value {user_record['flag']}")
                            unexpected_flag_value[user_history.pk] = user_record['flag']
                            continue
                    else:
                        # for any log that has domain removal message
                        # stay flexible with new change_messages or old message column for dry runs
                        if hasattr(user_history, 'change_messages'):
                            for_domain = user_history.change_messages.get(
                                'domain', {}
                            ).get(REMOVE_FROM_DOMAIN, {}).get('domain')
                        # domain removal message, if present, would be the only message in user_history.message
                        elif user_history.message and DOMAIN_REMOVE_REGEX.match(user_history.message):
                            for_domain = DOMAIN_REMOVE_REGEX.match(user_history.message).groups()[0]

                    if not for_domain and by_domain:
                        for_domain = by_domain

                if for_domain:
                    succeeded[user_history.pk] = (user_history.by_domain, for_domain)
                    _file.write(
                        f"{user_history.pk}, {user_history.user_type}, {user_history.user_id}, {by_domain}, {for_domain}, {user_history.change_messages}, {user_history.user_upload_record_id}\n"
                    )
                    if update_records:
                        user_history.for_domain = for_domain
                        user_history.save()


@memoized
def _get_commcare_users_domain(user_id):
    user = CommCareUser.get_by_user_id(user_id)
    if user:
        return user.domain


@memoized
def _get_user_bulk_upload_record(upload_record_id):
    return UserUploadRecord.objects.get(pk=upload_record_id)


@memoized
def _get_web_users_username_by_id(user_id):
    web_user = WebUser.get_by_user_id(user_id)
    if web_user:
        return web_user.username
