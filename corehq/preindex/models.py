from couchdbkit.ext.django import syncdb
from django.db.models import signals
from corehq.preindex import get_preindex_plugin


def catch_signal(sender, using=None, **kwargs):
    """Function used by syncdb signal"""
    if using != 'default':
        # only sync for the default DB
        return

    app_name = sender.label.rsplit('.', 1)[0]
    app_label = app_name.split('.')[-1]
    plugin = get_preindex_plugin(app_label)
    if plugin:
        plugin.sync_design_docs()

signals.pre_migrate.connect(catch_signal)
signals.post_syncdb.disconnect(syncdb)
