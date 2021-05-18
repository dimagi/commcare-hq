import math

from django.core.management import BaseCommand

from corehq.apps.analytics.tasks import _get_contact_ids_for_emails, \
    _delete_hubspot_contact, _get_contact_ids_for_email_domain
from corehq.apps.analytics.utils import (
    get_blocked_hubspot_domains,
    get_blocked_hubspot_email_domains,
    get_blocked_hubspot_accounts,
)
from corehq.apps.es import UserES
from corehq.util.metrics import metrics_gauge


class Command(BaseCommand):
    help = "Manually cleans up blocked hubspot contacts"

    def handle(self, **options):
        # First delete any user information from users that are members of
        # blocked domains
        blocked_domains = get_blocked_hubspot_domains()
        print("BLOCKED DOMAINS")
        print(blocked_domains)
        for domain in blocked_domains:
            print(f'\nDOMAIN  {domain}')
            user_query = UserES().domain(domain).source(['email', 'username'])

            total_users = user_query.count()
            chunk_size = 30  # Hubspot recommends fewer than 100 emails per request
            num_chunks = int(math.ceil(float(total_users) / float(chunk_size)))

            for chunk in range(num_chunks):
                blocked_users = (user_query
                                 .size(chunk_size)
                                 .start(chunk * chunk_size)
                                 .run()
                                 .hits)
                blocked_emails = []
                for user in blocked_users:
                    username = user.get('username')
                    user_email = user.get('email')
                    blocked_emails.append(username)
                    if user_email and user_email != username:
                        blocked_emails.append(user_email)
                ids_to_delete = _get_contact_ids_for_emails(set(blocked_emails))
                num_deleted = sum(
                    _delete_hubspot_contact(vid) for vid in ids_to_delete)
                if ids_to_delete:
                    print("IDS to DELETE")
                    print(ids_to_delete)
                    print("NUM DELETED", num_deleted)
                metrics_gauge(
                    'commcare.hubspot_data.deleted_user.blocked_domain',
                    num_deleted,
                    tags={
                        'domain': domain,
                        'ids_deleted': ids_to_delete,
                    }
                )

        # Next delete any user info from users that have emails or usernames ending
        # in blocked email-domains
        blocked_email_domains = get_blocked_hubspot_email_domains()
        for email_domain in blocked_email_domains:
            ids_to_delete = _get_contact_ids_for_email_domain(email_domain)
            print("ids to delete for email domain")
            print(ids_to_delete)
            num_deleted = sum(
                _delete_hubspot_contact(vid) for vid in ids_to_delete)
            metrics_gauge(
                'commcare.hubspot_data.deleted_user.blocked_email_domain',
                num_deleted,
                tags={
                    'email_domain': email_domain,
                    'ids_deleted': ids_to_delete,
                }
            )
