from django.contrib.auth.models import User
from django.core.management import BaseCommand

from django_prbac.models import Grant, Role, UserRole

from corehq import privileges


class Command(BaseCommand):
    help = 'Grants the user(s) specified the privilege to access global sms gateways'

    def add_arguments(self, parser):
        parser.add_argument(
            'usernames',
            nargs="*",
        )
        parser.add_argument(
            '--remove-user',
            action='store_true',
            default=False,
            help='Remove the users specified from the DEV_SUPPORT_TEAM privilege',
        )

    def handle(self, usernames, **options):
        dev_support_role = Role.objects.get_or_create(
            name="Dimagi Dev and Support Team",
            slug=privileges.DEV_SUPPORT_TEAM,
        )[0]
        global_sms_gateway_access = Role.objects.get_or_create(
            name="Accounting Admin",
            slug=privileges.GLOBAL_SMS_GATEWAY,
        )[0]
        if not dev_support_role.has_privilege(global_sms_gateway_access):
            Grant.objects.create(
                from_role=dev_support_role,
                to_role=global_sms_gateway_access,
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
                            to_role=dev_support_role
                        )
                        grant.delete()
                        print("Removed %s from the operations team"
                              % user.username)
                    except Grant.DoesNotExist:
                        print("The user %s was never part of the operations "
                              "team. Leaving alone." % user.username)
                elif not user_role.has_privilege(dev_support_role):
                    Grant.objects.create(
                        from_role=user_role.role,
                        to_role=dev_support_role,
                    )
                    print("Added %s to the Dev and Support team" % user.username)
                else:
                    print("User %s is already part of the Dev and Support team"
                          % user.username)

            except User.DoesNotExist:
                print("User %s does not exist" % username)
