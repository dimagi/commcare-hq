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
            if input("\n\ncommit the above changes?\n[y/N] ") == 'y':
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
    except UnicodeError:
        return latin_string


def fix_form(source):
    """Re-code non-printable substrings of Latin-1-decoded source as UTF-8

    Original problem: `source = utf8_bytes.decode('latin1')`

    The theory of the fix is that any non-ASCII UTF-8 character decoded
    as Latin-1 would end up as multiple Latin-1 characters, all being
    "unprintable" characters having a 1 as their most significant
    bit. This works because Latin-1 is a single-byte encoding (each
    character is encoded as a single 8-bit byte), while UTF-8 is a
    variable-width encoding where each character is encoded with 1 to 4
    bytes, and all bytes of multi-byte code points have a 1 as their
    most significant bit. Since the source string is XML, all non-ASCII
    character sequences will be followed by an XML delimiter, which
    always ends with a printable ASCII character (`>`).
    """
    new_source = ""
    unicode_block = ""
    for char in source:
        if char not in string.printable:
            unicode_block += char
        else:
            if unicode_block:
                transformed = latin_to_utf(unicode_block)
                new_source += transformed
                print("{} --> {}\n".format(unicode_block, transformed))
                unicode_block = ""
            new_source += char
    return new_source
