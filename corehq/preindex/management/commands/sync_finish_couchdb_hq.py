from __future__ import print_function
from __future__ import absolute_import
from __future__ import unicode_literals
from django.core.management.base import BaseCommand
from corehq.preindex import get_preindex_plugins


class Command(BaseCommand):
    help = 'Copy temporary design docs over existing ones'

    def handle(self, **options):
        for plugin in get_preindex_plugins():
            print("Copying design docs for plugin {}".format(plugin.app_label))
            plugin.copy_designs(temp='tmp')
