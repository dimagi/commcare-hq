# coding: utf-8
from __future__ import print_function
from __future__ import absolute_import
import getpass
from django.core.management.base import BaseCommand, CommandError
from email_validator import validate_email, EmailSyntaxError


class Command(BaseCommand):
    help = "Removes superuser/staff permission for given user"

    def add_arguments(self, parser):
        parser.add_argument(
            'username',
        )

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
            print(u"✓ User {} exists".format(couch_user.username))
        else:
            print(u"User {} doesn't exist or is not a webuser".format(couch_user.username))
            return

        is_superuser_changed = couch_user.is_superuser
        is_staff_changed = couch_user.is_staff
        couch_user.is_superuser = False
        couch_user.is_staff = False

        if is_superuser_changed or is_staff_changed:
            couch_user.save()
            print(u"✓ Superuser permissions have been removed for {}".format(couch_user.username))
        else:
            print("User was not a superuser or staff, no action required!")