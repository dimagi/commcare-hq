# django imports
from django.core.management.base import BaseCommand
from optparse import make_option

import urls

from auditcare.utils import show_urls


class Command(BaseCommand):
    args = ''
    help = """Output ALL views in your project in a format helpful for auditcare"""

    option_list = (
        make_option('--show-path', action='store_true', dest='show_path', default=False,
                    help='Show the URL paths, this is for informational purposes only'),
    )


    def handle(self, *args, **options):
        show_path = options["show_path"]
        consolidated = set(show_urls.show_urls(urls.urlpatterns))
        for raw_path, view_name in consolidated:
            path = raw_path.replace('^', '/').replace('$','')
            try:
                print '%s|"%s"' % (path, view_name)
                #print "%s\t%s" % (resolve_to_name(path), view_name)
            except Exception, ex:
                print ex
                pass





