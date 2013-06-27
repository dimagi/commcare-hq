from django.db.models import signals
import os
from dimagi.utils.couch.database import get_db
from dimagi.utils.couch import sync_docs


def get_couchapps():
    dir = os.path.abspath(os.path.dirname(__file__))
    return [d for d in os.listdir(dir) if os.path.isdir(os.path.join(dir, d))]


def sync_design_docs(db, temp=None):
    dir = os.path.abspath(os.path.dirname(__file__))
    for d in get_couchapps():
        sync_docs.sync_design_docs(db, os.path.join(dir, d), d, temp=temp)


def catch_signal(app, **kwargs):
    """Function used by syncdb signal"""
    app_name = app.__name__.rsplit('.', 1)[0]
    app_label = app_name.split('.')[-1]
    if app_label == "couchapps":
        sync_design_docs(get_db())


def copy_designs(db=None, temp='tmp', delete=True):
    db = db or get_db()
    for app_label in get_couchapps():
        sync_docs.copy_designs(db, app_label, temp=temp, delete=delete)


signals.post_syncdb.connect(catch_signal)
