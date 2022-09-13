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
            help='Remove the users specified from the Global SMS Gateway privilege',
        )

    def handle(self, usernames, **options):

        global_sms_gateway_access = Role.objects.get_or_create(
            name="Global SMS Gateway",
            slug=privileges.GLOBAL_SMS_GATEWAY,
        )[0]

        remove_user = options['remove_user']

        for username in usernames:
            try:
                user = User.objects.get(username=username)
                try:
                    user_role = UserRole.objects.get(user=user)
                except UserRole.DoesNotExist:
                    user_privs = Role.objects.get_or_create(
                        name=f"Privileges for {user.username}",
                        slug=f"{user.username}_privileges",
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
                            to_role=global_sms_gateway_access
                        )
                        grant.delete()
                        print(f"Removed Global SMS Gateway Edit Access Privilege for {user.username}")
                    except Grant.DoesNotExist:
                        print(f"The user {user.username} did not have the Privilege. Doing nothing here.")
                elif not user_role.has_privilege(global_sms_gateway_access):
                    Grant.objects.create(
                        from_role=user_role.role,
                        to_role=global_sms_gateway_access,
                    )
                    print(f"Enabled privilege to Edit Global SMS Gateways for the user {user.username}")
                else:
                    print(f"User {user.username} already have the requested privilege")

            except User.DoesNotExist:
                print(f"User {username} does not exist")
