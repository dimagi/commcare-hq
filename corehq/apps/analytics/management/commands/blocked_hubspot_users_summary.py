import math

from django.conf import settings
from django.core.management import BaseCommand

from corehq.apps.analytics.utils.hubspot import (
    get_blocked_hubspot_domains,
    get_first_conversion_status_for_emails,
)
from corehq.apps.es import UserES


class Command(BaseCommand):
    help = "Manually cleans up blocked Hubspot contacts"
    access_token = None

    def add_arguments(self, parser):
        parser.add_argument(
            '-s',
            '--skip',
            action='store',
            dest='skip',
            help='Skip to this domain name and check domains from there.',
        )
        parser.add_argument(
            '-d',
            '--domain',
            action='store',
            dest='domain',
            help='Only check this domain.',
        )

    def handle(self, **options):
        self.access_token = settings.ANALYTICS_IDS.get('HUBSPOT_ACCESS_TOKEN', None)

        if not self.access_token:
            self.stdout.write("No HubSpot access token found.")
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
                users_not_blocked.update(get_first_conversion_status_for_emails(
                    list(set(blocked_emails))
                ))
        if users_not_blocked:
            self.stdout.write(self.style.ERROR(
                f"\n\nFound {len(users_not_blocked)} users in "
                f"HubSpot who are members of the project {domain} "
                f"that is blocking HubSpot data:"
            ))
            self.stdout.write("\nEmail\tFirst Conversion")
            for user, status in users_not_blocked.items():
                self.stdout.write(f"{user}\t{status}")
            self.stdout.write('\n\n')
        else:
            self.stdout.write(self.style.SUCCESS(
                f"All users in project {domain} are absent on HubSpot."
            ))
