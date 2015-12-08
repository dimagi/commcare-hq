from couchdbkit.ext.django import syncdb
from django.db.models import signals, get_app
# here so django doesn't complain
from corehq.preindex.preindex_plugins import PREINDEX_PLUGINS


def catch_signal(sender, **kwargs):
    """Function used by syncdb signal"""
    app_name = sender.label.rsplit('.', 1)[0]
    app_label = app_name.split('.')[-1]
    if app_label in PREINDEX_PLUGINS:
        PREINDEX_PLUGINS[app_label].sync_design_docs()
    syncdb(get_app(sender.label), None, **kwargs)


signals.post_migrate.connect(catch_signal)
