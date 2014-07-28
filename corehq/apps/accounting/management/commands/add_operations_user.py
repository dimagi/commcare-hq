# Use modern Python
from __future__ import unicode_literals, absolute_import, print_function

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
        remove_user = options.get('remove_user', False)

        for arg in args:
            try:
                user = User.objects.get(username=arg)
                user_privs = Role.objects.get_or_create(
                    name="Privileges for %s" % user.username,
                    slug="%s_privileges" % user.username,
                )[0]
                try:
                    user_role = UserRole.objects.get(user=user)
                    if user_role.role.id != user_privs.id:
                        confirm = raw_input(
                            "Are you sure you want to update role for %s? "
                            "Type 'yes' to continue.\n" % user.username
                        )
                        if confirm != 'yes':
                            continue
                    user_role.role = user_privs
                    user_role.save()
                    print ("Updated user role for %s" % user.username)
                except UserRole.DoesNotExist:
                    UserRole.objects.create(
                        user=user,
                        role=user_privs,
                    )

                if remove_user:
                    try:
                        # remove grant object
                        grant = Grant.objects.get(
                            from_role=user_privs,
                            to_role=ops_role
                        )
                        grant.delete()
                        print("Removed %s from the operations team"
                              % user.username)
                    except Grant.DoesNotExist:
                        print("The user %s was never part of the operations "
                              "team. Leaving alone." % user.username)
                elif not user_privs.has_privilege(ops_role):
                    Grant.objects.create(
                        from_role=user_privs,
                        to_role=ops_role,
                    )
                    print("Added %s to the operations team" % user.username)
                else:
                    print("User %s is already part of the operations team"
                          % user.username)

            except User.DoesNotExist:
                print("User %s does not exist" % arg)
