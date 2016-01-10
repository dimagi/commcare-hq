from abc import ABCMeta, abstractmethod
import os

from dimagi.utils.couch.database import get_db
from dimagi.utils.couch.sync_docs import DesignInfo


PREINDEX_PLUGINS = {}


def register_preindex_plugin(plugin):
    PREINDEX_PLUGINS[plugin.app_label] = plugin


class PreindexPlugin(object):

    __metaclass__ = ABCMeta

    synced = False

    @abstractmethod
    def _get_designs(self):
        raise NotImplementedError()

    def get_designs(self):
        used = set()
        designs = []
        for design in self._get_designs():
            key = (design.db.uri, design.app_label)
            if key not in used:
                designs.append(design)
            used.add(key)
        return designs

    @classmethod
    def register(cls, *args, **kwargs):
        register_preindex_plugin(cls(*args, **kwargs))

    def sync_design_docs(self, temp=None):
        from corehq.preindex.accessors import sync_design_doc
        if self.synced:
            # workaround emit_post_sync_signal called twice
            # https://code.djangoproject.com/ticket/17977
            # this is to speed up test initialization
            return
        self.synced = True
        for design in self.get_designs():
            sync_design_doc(design, temp=temp)

    def copy_designs(self, temp=None, delete=True):
        from corehq.preindex.accessors import copy_design_doc
        for design in self.get_designs():
            copy_design_doc(design, temp=temp, delete=delete)

    def __repr__(self):
        return '{cls.__name__}({self.app_label!r}, {self.dir!r})'.format(
            cls=self.__class__,
            self=self,
        )

    def __init__(self, app_label, file):
        # once the fluff part of this has been merged we can get rid of this
        # this is just to make it easy for me in the meantime
        assert 'FluffPreindexPlugin' == self.__class__.__name__
        self.app_label = app_label
        self.dir = os.path.abspath(os.path.dirname(file))


def get_dbs_from_app_label_and_map(app_label, app_db_map):
    if app_db_map and app_label in app_db_map:
        db_names = app_db_map[app_label]
        if not isinstance(db_names, (list, tuple, set)):
            db_names = [db_names]

        return [get_db(db_name) for db_name in set(db_names)]
    return [get_db()]


class CouchAppsPreindexPlugin(PreindexPlugin):
    """
    :param app_label:   The app label for the top level application.
    :param dir:         The directory of the top level application.
    :param app_db_map:  A dictionary mapping child apps to couch databases.
                        e.g. {'my_app': 'meta'} will result in 'my_app' being synced
                        to the '{main_db}__meta' database.

    use e.g.
        CouchAppsPreindexPlugin.register('couchapps', __file__, {
            'myview': <list of db slugs to sync to>
            ...
        })
    to register a module as a couchapps root

    """
    def __init__(self, app_label, file, app_db_map=None):
        self.app_label = app_label
        self.dir = os.path.abspath(os.path.dirname(file))
        self.app_db_map = app_db_map

    def get_couchapps(self):
        return [d for d in os.listdir(self.dir)
                if os.path.isdir(os.path.join(self.dir, d))]

    def _get_designs(self):
        return [
            DesignInfo(app_label=app_label, db=db,
                       design_path=os.path.join(self.dir, app_label))
            for app_label in self.get_couchapps()
            for db in self.get_dbs(app_label)
        ]

    def get_dbs(self, app_label):
        return get_dbs_from_app_label_and_map(app_label, self.app_db_map)


class ExtraPreindexPlugin(PreindexPlugin):
    """
    ExtraPreindexPlugin.register('myapp', __file__, <list of db slugs to sync to>)
    """
    def __init__(self, app_label, file, db_names=None):
        self.app_label = app_label
        self.dir = os.path.abspath(os.path.dirname(file))
        self.db_names = db_names

    def _get_designs(self):
        return [
            DesignInfo(
                app_label=self.app_label,
                db=db,
                design_path=os.path.join(self.dir, "_design")
            )
            for db in self.get_dbs(self.app_label)
        ]

    def get_dbs(self, app_label):
        return get_dbs_from_app_label_and_map(app_label, {app_label: self.db_names})
