from django.contrib.auth.models import User
from django.core.management import BaseCommand
from corehq import privileges
from django_prbac.models import UserRole, Role


class Command(BaseCommand):
    help = 'Grants the user(s) specified the DIMAGI_OPERATIONS_TEAM privilege'

    def handle(self, *args, **options):
        for arg in args:
            try:
                user = User.objects.get(username=arg)
                accounting_role = Role.objects.get_or_create(
                    name="Dimagi Operations Team",
                    slug=privileges.DIMAGI_OPERATIONS_TEAM,
                )[0]
                user_role, is_new = UserRole.objects.get_or_create(
                    user=user,
                    role=accounting_role
                )
                if not is_new:
                    print "User %s was already part of the operations team" % arg
                else:
                    print "User %s was added to the operations team" % arg
            except User.DoesNotExist:
                print "User %s does not exist" % arg
