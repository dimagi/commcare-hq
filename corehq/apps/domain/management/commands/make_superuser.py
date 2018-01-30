# coding: utf-8
from __future__ import print_function
from __future__ import absolute_import
import getpass
from django.core.management.base import BaseCommand, CommandError
from email_validator import validate_email, EmailSyntaxError


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
            password = self.get_password_from_user()
            couch_user = WebUser.create(None, username, password)
            print(u"→ User {} created".format(couch_user.username))

        is_superuser_changed = not couch_user.is_superuser
        is_staff_changed = not couch_user.is_staff
        couch_user.is_superuser = True
        couch_user.is_staff = True

        if is_superuser_changed or is_staff_changed:
            couch_user.save()

        if is_superuser_changed:
            print(u"→ User {} is now a superuser".format(couch_user.username))
        else:
            print(u"✓ User {} is a superuser".format(couch_user.username))

        if is_staff_changed:
            print(u"→ User {} can now access django admin".format(couch_user.username))
        else:
            print(u"✓ User {} can access django admin".format(couch_user.username))
