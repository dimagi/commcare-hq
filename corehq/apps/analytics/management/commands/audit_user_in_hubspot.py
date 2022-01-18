from django.core.management import BaseCommand

from corehq.apps.analytics.utils import (
    get_blocked_hubspot_domains,
    get_first_conversion_status_for_emails,
    ALLOWED_CONVERSIONS,
)
from corehq.apps.users.models import WebUser, Invitation


class Command(BaseCommand):
    help = "Audit a web user's HubSpot status in HubSpot and CommCare HQ"

    def add_arguments(self, parser):
        parser.add_argument('email')

    def handle(self, email, **options):
        web_user = WebUser.get_by_username(email)
        if not web_user:
            self.stdout.write(self.style.ERROR(
                "User not does not exist on CommCare HQ."
            ))
            return

        blocked_domains = set(get_blocked_hubspot_domains())

        user_domains = set(web_user.get_domains())
        blocked_memberships = user_domains.intersection(blocked_domains)

        if not blocked_memberships:
            self.show_status_of_possibly_unblocked_user(email, blocked_domains)
        else:
            self.show_status_of_blocked_user(email, blocked_memberships)

        self.display_first_conversion_status(email)

    def show_status_of_possibly_unblocked_user(self, email, blocked_domains):
        self.stdout.write(
            f"\n{email} is not a member of any projects actively blocking "
            f"data from HubSpot.\n"
        )
        blocked_domains_invited = Invitation.objects.filter(
            domain__in=list(blocked_domains),
            is_accepted=True,
            email=email,
        ).values_list('email', flat=True)
        if blocked_domains_invited:
            self.stdout.write(
                "However, it looks like they have previously accepted "
                "invitations to the following project(s) blocking HubSpot data:"
            )
            self.stdout.write("\n".join(blocked_domains_invited))
        else:
            self.stdout.write(
                "They also have never accepted an invitation from a project "
                "that is actively blocking HubSpot data."
            )
        self.stdout.write("\n")

    def show_status_of_blocked_user(self, email, blocked_memberships):
        self.stdout.write(
            f"\n{email} is a member of the following project(s) actively "
            f"blocking data from HubSpot:"
        )
        self.stdout.write("\n".join(blocked_memberships))
        self.stdout.write("\n")

    def display_first_conversion_status(self, email):
        hubspot_contact_info = get_first_conversion_status_for_emails([email])
        if hubspot_contact_info:
            first_conversion = hubspot_contact_info[email]
            self.stdout.write(
                f"\n{email} found in HubSpot with First Conversion "
                f"(clustered) as '{first_conversion}'.\n"
            )
            if first_conversion in ALLOWED_CONVERSIONS:
                self.stdout.write(
                    "This is fully acceptable according to our policy."
                )
            else:
                self.stdout.write(
                    "If the user is part of a project blocking HubSpot data, "
                    "then this is not allowed."
                )
        else:
            self.stdout.write(
                f"{email} not found in HubSpot."
            )
        self.stdout.write("\n")
