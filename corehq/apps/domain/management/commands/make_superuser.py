# coding: utf-8
from __future__ import absolute_import, unicode_literals

import getpass
import logging

from django.core.management.base import BaseCommand, CommandError

from email_validator import EmailSyntaxError, validate_email

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
            password = self.get_password_from_user()
            couch_user = WebUser.create(None, username, password)
            logger.info("→ User {} created".format(couch_user.username))

        is_superuser_changed = not couch_user.is_superuser
        is_staff_changed = not couch_user.is_staff
        couch_user.is_superuser = True
        couch_user.is_staff = True

        if is_superuser_changed or is_staff_changed:
            couch_user.save()

        if is_superuser_changed:
            logger.info("→ User {} is now a superuser".format(couch_user.username))
        else:
            logger.info("✓ User {} is a superuser".format(couch_user.username))

        if is_staff_changed:
            logger.info("→ User {} can now access django admin".format(couch_user.username))
        else:
            logger.info("✓ User {} can access django admin".format(couch_user.username))
