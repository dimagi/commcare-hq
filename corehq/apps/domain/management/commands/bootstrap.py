# coding: utf-8
from __future__ import print_function
from __future__ import absolute_import
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Tell user to use make_superuser"

    def add_arguments(self, parser):
        parser.add_argument(
            'domain_name',
        )
        parser.add_argument(
            'username',
        )
        parser.add_argument(
            'passwd',
        )

    def handle(self, domain_name, username, passwd, **options):
        print(u"The bootstrap command doesn't exist anymore. "
              u"Please use `./manage.py make_superuser {username}` "
              u"and then create a domain in the UI instead.".format(username=username))
