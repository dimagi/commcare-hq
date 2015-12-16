from django.core.management.base import BaseCommand
from corehq.preindex import get_preindex_plugins


class Command(BaseCommand):
    help = 'Copy temporary design docs over existing ones'

    def handle(self, *args, **options):
        for preindex_plugin in get_preindex_plugins():
            plugin_class_name = preindex_plugin.__class__.__name__
            if plugin_class_name == 'DefaultPreindexPlugin':
                print "Syncing design docs for {}".format(preindex_plugin.app_label)
            else:
                print "Syncing design docs for {} (using {})".format(
                    preindex_plugin.app_label, plugin_class_name)
            preindex_plugin.sync_design_docs()
