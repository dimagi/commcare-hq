import logging

from django.core.management.base import BaseCommand, CommandError

from email_validator import EmailSyntaxError, validate_email

from corehq.util.signals import signalcommand

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Grant or remove permission to change superuser and staff status."

    def add_arguments(self, parser):
        parser.add_argument('username', type=str)
        parser.add_argument('--grant', action='store_true', help="grant permission")
        parser.add_argument('--revoke', action='store_true', help='revoke permission')

    @signalcommand
    def handle(self, username, **options):
        from corehq.apps.users.models import WebUser
        try:
            validate_email(username)
        except EmailSyntaxError:
            raise CommandError('Your username must be an email address')
        couch_user = WebUser.get_by_username(username)

        if couch_user:
            if not isinstance(couch_user, WebUser):
                raise CommandError('Username already in use by a non-web user')
            logger.info("✓ User {} exists".format(couch_user.username))
        else:
            raise CommandError('Please enter a valid Dimagi email address')

        if options['grant']:
            is_permission_changed = not couch_user.can_assign_superuser
            couch_user.can_assign_superuser = True
            if is_permission_changed:
                couch_user.save()
                logger.info("→ User {} can now assign superuser and staff roles".format(couch_user.username))
            else:
                logger.info("→ User {} can assign superuser and staff roles".format(couch_user.username))
        elif options['revoke']:
            is_permission_changed = couch_user.can_assign_superuser
            couch_user.can_assign_superuser = False
            if is_permission_changed:
                couch_user.save()
                logger.info("→ User {} now cannot assign superuser and staff roles".format(couch_user.username))
            else:
                logger.info("→ User {} cannot assign superuser and staff roles".format(couch_user.username))
