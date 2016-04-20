import os
import re
from django.conf import settings
from django.core.management.base import LabelCommand


class Command(LabelCommand):
    """
    Comments out untranslated plural strings due to a bug in tx push.
    See http://manage.dimagi.com/default.asp?224619 for details.
    """
    help = ""
    args = ""

    def handle_po_file(self, filepath):
        with open(filepath, 'r') as f:
            content = f.read()
            regex = re.compile('(#(.+\n)#(.+\n)msgid(.+\n)+msgid_plural(.+\n)+msgstr\[0\] ""\nmsgstr\[1\] ""\n\n)')
            for matches in regex.findall(content):
                string = matches[0]
                content = content.replace(string, '')

        with open(filepath, 'w') as f:
            f.write(content)

    def handle(self, *args, **options):
        root_dir = settings.FILEPATH
        locale_dir = os.path.join(root_dir, 'locale')
        for path, dirs, files in os.walk(locale_dir):
            for filename in files:
                if filename.endswith('.po'):
                    self.handle_po_file(os.path.join(path, filename))
