import os
from couchdbkit.ext.django.loading import get_db
# corehq dependency is simplest of a few annoying options
# - move this code into corehq
# - extract corehq.preindex into its own project
# - be ok with intentionally introducing this dependency
#   for something that's pretty bound to our specific deploy workflow
from corehq.preindex import PreindexPlugin
from pillowtop.utils import get_all_pillows
from dimagi.utils.couch import sync_docs


class FluffPreindexPlugin(PreindexPlugin):
    def sync_design_docs(self, temp=None):
        synced = set()
        for pillow in get_all_pillows(instantiate=False):
            if hasattr(pillow, 'indicator_class'):
                app_label = pillow.indicator_class._meta.app_label
                db = get_db(app_label)
                key = (self.dir, app_label, db)
                if key not in synced:
                    sync_docs.sync_design_docs(
                        db=db,
                        design_dir=os.path.join(self.dir, "_design"),
                        design_name=self.app_label,
                        temp=temp,
                    )
                    synced.add(key)

    def copy_designs(self, temp=None, delete=True):
        for pillow in get_all_pillows(instantiate=False):
            if hasattr(pillow, 'indicator_class'):
                app_label = pillow.indicator_class._meta.app_label
                db = get_db(app_label)
                sync_docs.copy_designs(
                    db=db,
                    design_name=self.app_label,
                    temp=temp,
                    delete=delete,
                )


FluffPreindexPlugin.register('fluff', __file__)
