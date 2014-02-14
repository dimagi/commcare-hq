from optparse import make_option
from django.contrib.auth.models import User
from django.core.management import BaseCommand
from corehq import privileges
from django_prbac.models import UserRole, Role, Grant


class Command(BaseCommand):
    help = 'Grants the user(s) specified the DIMAGI_OPERATIONS_TEAM privilege'

    option_list = BaseCommand.option_list + (
        make_option('--remove-user', action='store_true',  default=False,
                    help='Remove the users specified from the DIMAGI_OPERATIONS_TEAM privilege'),
    )

    def handle(self, *args, **options):
        ops_role = Role.objects.get_or_create(
            name="Dimagi Operations Team",
            slug='dimagi_ops',
        )[0]
        accounting_admin = Role.objects.get_or_create(
            name="Accounting Admin",
            slug=privileges.ACCOUNTING_ADMIN,
        )[0]
        if not ops_role.has_privilege(accounting_admin):
            Grant.objects.create(
                from_role=ops_role,
                to_role=accounting_admin,
            )

        for arg in args:
            try:
                user = User.objects.get(username=arg)
                user_role, is_new = UserRole.objects.get_or_create(
                    user=user,
                    role=ops_role,
                )
                if options.get('remove_user', False):
                    user_role.delete()
                    print "User %s was removed from the operations team" % arg
                elif not is_new:
                    print "User %s was already part of the operations team" % arg
                else:
                    print "User %s was added to the operations team" % arg
            except User.DoesNotExist:
                print "User %s does not exist" % arg
