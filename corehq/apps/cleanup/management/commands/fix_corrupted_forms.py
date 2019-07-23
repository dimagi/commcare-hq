# encoding: utf-8
from __future__ import absolute_import, print_function, unicode_literals

import string

from django.core.management import BaseCommand

from six.moves import input

from corehq.apps.app_manager.dbaccessors import get_app


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('app_id')
        parser.add_argument('form_id')

    # https://dimagi-dev.atlassian.net/browse/HI-747
    def handle(self, domain, app_id, form_id, **options):
        app = get_app(domain, app_id)
        form = app.get_form(form_id)
        old_source = form.source
        new_source = fix_form(old_source)
        if old_source != new_source:
            if input("commit the above changes?\n[y/N] ") == 'y':
                form.source = new_source
                app.save()
                print("saved")
            else:
                print("aborting")
        else:
            print("There was no change")


def latin_to_utf(latin_string):
    try:
        return latin_string.encode('latin1').decode('utf-8')
    except:
        return latin_string


def fix_form(source):
    new_source = ""
    unicode_block = ""
    for char in source:
        if char not in string.printable:
            unicode_block += char
        else:
            if unicode_block:
                transformed = latin_to_utf(unicode_block)
                new_source += transformed
                print("{} --> {}".format(unicode_block, transformed))
                unicode_block = ""
            new_source += char
    return new_source
