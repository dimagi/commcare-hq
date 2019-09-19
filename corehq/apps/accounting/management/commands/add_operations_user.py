# Use modern Python

from django.contrib.auth.models import User
from django.core.management import BaseCommand

from django_prbac.models import Grant, Role, UserRole

from corehq import privileges


class Command(BaseCommand):
    help = 'Grants the user(s) specified the DIMAGI_OPERATIONS_TEAM privilege'

    def add_arguments(self, parser):
        parser.add_argument(
            'usernames',
            nargs="*",
        )
        parser.add_argument(
            '--remove-user',
            action='store_true',
            default=False,
            help='Remove the users specified from the DIMAGI_OPERATIONS_TEAM privilege',
        )

    def handle(self, usernames, **options):
        ops_role = Role.objects.get_or_create(
            name="Dimagi Operations Team",
            slug=privileges.OPERATIONS_TEAM,
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
        remove_user = options['remove_user']

        for username in usernames:
            try:
                user = User.objects.get(username=username)
                try:
                    user_role = UserRole.objects.get(user=user)
                except UserRole.DoesNotExist:
                    user_privs = Role.objects.get_or_create(
                        name="Privileges for %s" % user.username,
                        slug="%s_privileges" % user.username,
                    )[0]
                    user_role = UserRole.objects.create(
                        user=user,
                        role=user_privs,
                    )

                if remove_user:
                    try:
                        # remove grant object
                        grant = Grant.objects.get(
                            from_role=user_role.role,
                            to_role=ops_role
                        )
                        grant.delete()
                        print("Removed %s from the operations team"
                              % user.username)
                    except Grant.DoesNotExist:
                        print("The user %s was never part of the operations "
                              "team. Leaving alone." % user.username)
                elif not user_role.has_privilege(ops_role):
                    Grant.objects.create(
                        from_role=user_role.role,
                        to_role=ops_role,
                    )
                    print("Added %s to the operations team" % user.username)
                else:
                    print("User %s is already part of the operations team"
                          % user.username)

            except User.DoesNotExist:
                print("User %s does not exist" % username)
