# django imports
from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals
from django.core.management.base import BaseCommand
from optparse import make_option

import urls

from auditcare.utils import show_urls


class Command(BaseCommand):
    help = """Output ALL views in your project in a format helpful for auditcare"""

    def handle(self, **options):
        consolidated = set(show_urls.show_urls(urls.urlpatterns))
        for raw_path, view_name in consolidated:
            path = raw_path.replace('^', '/').replace('$', '')
            try:
                print('%s|"%s"' % (path, view_name))
                #print "%s\t%s" % (resolve_to_name(path), view_name)
            except Exception as ex:
                print(ex)
                pass





