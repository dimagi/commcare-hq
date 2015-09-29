from couchdbkit.ext.django import syncdb
from django.db.models import signals, get_app
import os
from dimagi.utils.couch.database import get_db
from dimagi.utils.couch import sync_docs
from dimagi.utils.couch.sync_docs import DesignInfo


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

    def get_designs(self):
        raise NotImplementedError()

    def sync_design_docs(self, temp=None):
        synced = set()
        for design in self.get_designs():
            key = (design.db.uri, design.app_label)
            if key not in synced:
                sync_docs.sync_design_docs(
                    db=design.db,
                    design_dir=design.design_path,
                    design_name=design.app_label,
                    temp=temp,
                )
                synced.add(key)

    def copy_designs(self, temp=None, delete=True):
        copied = set()
        for design in self.get_designs():
            key = (design.db.uri, design.app_label)
            if key not in copied:
                sync_docs.copy_designs(
                    db=design.db,
                    design_name=design.app_label,
                    temp=temp,
                    delete=delete,
                )
                copied.add(key)

    def __repr__(self):
        return '{cls.__name__}({self.app_label!r}, {self.dir!r})'.format(
            cls=self.__class__,
            self=self,
        )


def get_dbs_from_app_label_and_map(app_label, app_db_map):
    if app_db_map and app_label in app_db_map:
        db_names = app_db_map[app_label]
        if not isinstance(db_names, (list, tuple)):
            db_names = [db_names]
        return [get_db(db_name) for db_name in db_names]
    return [get_db()]


class CouchAppsPreindexPlugin(PreindexPlugin):
    """
    :param app_label:   The app label for the top level application.
    :param dir:         The directory of the top level application.
    :param app_db_map:  A dictionary mapping child apps to couch databases.
                        e.g. {'my_app': 'meta'} will result in 'my_app' being synced
                        to the '{main_db}__meta' database.
    """

    def get_couchapps(self):
        return [d for d in os.listdir(self.dir)
                if os.path.isdir(os.path.join(self.dir, d))]

    def get_designs(self):
        return [
            DesignInfo(app_label=app_label, db=db,
                       design_path=os.path.join(self.dir, app_label))
            for app_label in self.get_couchapps()
            for db in get_dbs_from_app_label_and_map(app_label, self.app_db_map)
        ]


class ExtraPreindexPlugin(PreindexPlugin):

    def get_designs(self):
        return [
            DesignInfo(
                app_label=self.app_label,
                db=db,
                design_path=os.path.join(self.dir, "_design")
            )
            for db in get_dbs_from_app_label_and_map(self.app_label, self.app_db_map)
        ]

    @classmethod
    def register(cls, app_label, file, db_names):
        super(ExtraPreindexPlugin, cls).register(app_label, file, {app_label: db_names})


def get_preindex_plugins():
    return PREINDEX_PLUGINS.values()


def catch_signal(sender, **kwargs):
    """Function used by syncdb signal"""
    app_name = sender.label.rsplit('.', 1)[0]
    app_label = app_name.split('.')[-1]
    if app_label in PREINDEX_PLUGINS:
        PREINDEX_PLUGINS[app_label].sync_design_docs()
    syncdb(get_app(sender.label), None, **kwargs)


signals.post_migrate.connect(catch_signal)
