from django.core.management.base import BaseCommand

from corehq.apps.users.models import WebUser

from corehq.apps.users.models import Invitation, CouchUser


class Command(BaseCommand):
    help = "Accepts an invite into a domain for an existing web user"

    def add_arguments(self, parser):
        parser.add_argument('username')
        parser.add_argument('domain')

    def handle(self, username, domain, **options):
        try:
            invitation = Invitation.objects.get(domain=domain, email=username, is_accepted=False)
        except:
            print("No invites found for %s in Project Space (%s)" % (username, domain))
            return

        user = CouchUser.get_by_username(username)
        if not user:
            print("No existing web users active for email address %s. This command can only activate existing web users" % username)
            return

        print("Accepting %s's invite to Project Space(%s)" % (username, domain))

        user.add_as_web_user(invitation.domain, role=invitation.role,
                                location_id=invitation.location_id, program_id=invitation.program)
        invitation.is_accepted = True
        invitation.save()
        print("Operation completed")
