import getpass
import logging

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.core.validators import ValidationError, validate_email

from corehq.apps.hqadmin.views.users import send_email_notif
from corehq.util.signals import signalcommand

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Make a new superuser or make an existing user a superuser."

    def add_arguments(self, parser):
        parser.add_argument(
            'username',
        )

    @staticmethod
    def get_password_from_user():
        while True:
            password = getpass.getpass('Create New Password:')
            if password == getpass.getpass('Repeat Password:'):
                return password

    @signalcommand
    def handle(self, username, **options):
        if not settings.ALLOW_MAKE_SUPERUSER_COMMAND:
            from dimagi.utils.web import get_site_domain
            raise CommandError(f"""You cannot run this command in SaaS Enviornments.
            Use https://{get_site_domain()}/hq/admin/superuser_management/ for granting superuser permissions""")
        from corehq.apps.users.models import WebUser
        try:
            validate_email(username)
        except ValidationError as exc:
            raise CommandError('The username must be a valid email address') from exc
        couch_user = WebUser.get_by_username(username)
        if couch_user:
            if not isinstance(couch_user, WebUser):
                raise CommandError('Username already in use by a non-web user')
            logger.info("✓ User {} exists".format(couch_user.username))
        else:
            password = self.get_password_from_user()
            couch_user = WebUser.create(None, username, password, created_by=None, created_via=__name__,
                                        by_domain_required_for_log=False)
            logger.info("→ User {} created".format(couch_user.username))

        is_superuser_changed = not couch_user.is_superuser
        is_staff_changed = not couch_user.is_staff
        can_assign_superuser_changed = not couch_user.can_assign_superuser
        couch_user.is_superuser = True
        couch_user.is_staff = True
        couch_user.can_assign_superuser = True

        if is_superuser_changed or is_staff_changed or can_assign_superuser_changed:
            couch_user.save()

        fields_changed = {'email': couch_user.username}

        if is_superuser_changed:
            logger.info("→ User {} is now a superuser".format(couch_user.username))
            fields_changed['is_superuser'] = couch_user.is_superuser
        else:
            logger.info("✓ User {} is a superuser".format(couch_user.username))
            fields_changed['same_superuser'] = couch_user.is_superuser

        if is_staff_changed:
            logger.info("→ User {} can now access django admin".format(couch_user.username))
            fields_changed['is_staff'] = couch_user.is_staff
        else:
            logger.info("✓ User {} can access django admin".format(couch_user.username))
            fields_changed['same_staff'] = couch_user.is_staff

        if can_assign_superuser_changed:
            logger.info("→ User {} can now assign superuser privilege".format(couch_user.username))
            fields_changed['can_assign_superuser'] = couch_user.can_assign_superuser
        else:
            logger.info("✓ User {} can assign superuser privilege".format(couch_user.username))
            fields_changed['same_management_privilege'] = couch_user.can_assign_superuser

        send_email_notif([fields_changed], changed_by_user='The make_superuser command')
