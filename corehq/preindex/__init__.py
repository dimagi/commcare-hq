from couchdbkit.ext.django import syncdb
from django.db.models import signals, get_app
import os
from south.signals import post_migrate
from dimagi.utils.couch.database import get_db
from dimagi.utils.couch import sync_docs


PREINDEX_PLUGINS = {}


def register_preindex_plugin(plugin):
    PREINDEX_PLUGINS[plugin.app_label] = plugin


class PreindexPlugin(object):

    def __init__(self, app_label, dir, app_db_map=None):
        self.app_label = app_label
        self.dir = dir
        self.app_db_map = app_db_map

    @classmethod
    def register(cls, app_label, file, app_db_map=None):
        """
        use
            <PreindexPlugin subclass>.register(<app_label>, __file__)
        to register a module as a couchapps root

        """
        dir = os.path.abspath(os.path.dirname(file))
        register_preindex_plugin(cls(app_label, dir, app_db_map))

    def sync_design_docs(self, temp=None):
        raise NotImplementedError()

    def copy_designs(self, temp=None, delete=True):
        raise NotImplementedError()

    def __repr__(self):
        return '{cls.__name__}({self.app_label!r}, {self.dir!r})'.format(
            cls=self.__class__,
            self=self,
        )


class CouchAppsPreindexPlugin(PreindexPlugin):
    """
    :param app_label:   The app label for the top level application.
    :param dir:         The directory of the top level application.
    :param app_db_map:  A dictionary mapping child apps to couch databases.
                        e.g. {'my_app': 'meta'} will result in 'my_app' being synced
                        to the '{main_db}__meta' database.
    """
    def __init__(self, app_label, dir, app_db_map=None):
        super(CouchAppsPreindexPlugin, self).__init__(app_label, dir, app_db_map)

    def db(self, app_label):
        if self.app_db_map and app_label in self.app_db_map:
            return get_db(self.app_db_map[app_label])
        return get_db()

    def get_couchapps(self):
        return [d for d in os.listdir(self.dir)
                if os.path.isdir(os.path.join(self.dir, d))]

    def sync_design_docs(self, temp=None):
        for app_label in self.get_couchapps():
            sync_docs.sync_design_docs(
                db=self.db(app_label),
                design_dir=os.path.join(self.dir, app_label),
                design_name=app_label,
                temp=temp,
            )

    def copy_designs(self, temp=None, delete=True):
        for app_label in self.get_couchapps():
            sync_docs.copy_designs(
                db=self.db(app_label),
                design_name=app_label,
                temp=temp,
                delete=delete,
            )


def get_preindex_plugins():
    return PREINDEX_PLUGINS.values()


def catch_signal(app, **kwargs):
    """Function used by syncdb signal"""
    app_name = app.__name__.rsplit('.', 1)[0]
    app_label = app_name.split('.')[-1]
    if app_label in PREINDEX_PLUGINS:
        PREINDEX_PLUGINS[app_label].sync_design_docs()


signals.post_syncdb.connect(catch_signal)

# and totally unrelatedly...


def sync_south_app(app, **kwargs):
    syncdb(get_app(app), None, **kwargs)


post_migrate.connect(sync_south_app)
