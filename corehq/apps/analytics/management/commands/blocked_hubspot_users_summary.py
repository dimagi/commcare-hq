import math
import requests

from django.conf import settings
from django.core.management import BaseCommand

from corehq.apps.analytics.utils import (
    get_blocked_hubspot_domains,
    MAX_API_RETRIES,
)
from corehq.apps.es import UserES


class Command(BaseCommand):
    help = "Manually cleans up blocked Hubspot contacts"
    api_key = None

    def add_arguments(self, parser):
        parser.add_argument(
            '-s',
            '--skip',
            action='store',
            dest='skip',
            help='Skip to this domain name and check domains from there.',
        )
        parser.add_argument(
            '-s',
            '--domain',
            action='store',
            dest='domain',
            help='Only check this domain.',
        )

    def handle(self, **options):
        self.api_key = settings.ANALYTICS_IDS.get('HUBSPOT_API_KEY', None)

        if not self.api_key:
            self.stdout.write("No HubSpot API key found.")
            return

        blocked_domains = get_blocked_hubspot_domains()

        check_domain = options.get('domain')
        skip_to_domain = options.get('skip')

        if check_domain:
            if check_domain not in blocked_domains:
                self.stdout.write(
                    f"{check_domain} is not a blocked HubSpot domain."
                )
                return
            self.print_domain_summary(check_domain)
        else:
            skip = skip_to_domain is not None

            for domain in blocked_domains:
                if domain == skip_to_domain:
                    skip = False
                if skip:
                    continue
                self.print_domain_summary(domain)

    def print_domain_summary(self, domain):
        users_not_blocked = {}
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
                users_not_blocked.update(self.get_blocked_status_for_emails(
                    list(set(blocked_emails))
                ))
        if users_not_blocked:
            self.stdout.write(self.style.ERROR(
                f"\n\nFound {len(users_not_blocked)} users in "
                f"HubSpot who are members of the project {domain} "
                f"that is blocking HubSpot data:"
            ))
            self.stdout.write("\nEmail\tFirst Conversion")
            for user, status in users_not_blocked:
                self.stdout.write(f"{user}\t{status}")
            self.stdout.write('\n\n')
        else:
            self.stdout.write(self.style.SUCCESS(
                f"All users in project {domain} are absent on HubSpot."
            ))

    def get_blocked_status_for_emails(self, list_of_emails, retry_num=0):
        try:
            req = requests.get(
                "https://api.hubapi.com/contacts/v1/contact/emails/batch/",
                params={
                    'hapikey': self.api_key,
                    'email': list_of_emails,
                },
            )
            if req.status_code == 404:
                return {}
            req.raise_for_status()
        except (ConnectionError, requests.exceptions.HTTPError) as e:
            if retry_num <= MAX_API_RETRIES:
                return self.get_blocked_status_for_emails(list_of_emails, retry_num + 1)
            else:
                self.stdout.write(self.style.ERROR(
                    f"Failed to get data from hubspot for "
                    f"{list_of_emails.join(',')}."
                ))
        else:
            status_summary = {}
            for contact_id, data in req.json().items():
                first_conversion_status = data.get(
                    'properties', {}
                ).get('first_conversion_clustered_', {}).get('value')
                email = data.get(
                    'properties', {}
                ).get('email', {}).get('value')
                status_summary[email] = first_conversion_status
            return status_summary
        return {}
