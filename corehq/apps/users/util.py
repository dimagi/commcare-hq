import re

from django.conf import settings
from django.contrib.auth.models import User

from couchdbkit.resource import ResourceNotFound

from dimagi.utils.couch.database import get_db



def cc_user_domain(domain):
    sitewide_domain = settings.HQ_ACCOUNT_ROOT 
    return ("%s.%s" % (domain, sitewide_domain)).lower()

def format_username(username, domain):
    return "%s@%s" % (username.lower(), cc_user_domain(domain))

def normalize_username(username, domain=None):
    from django.core.validators import validate_email

    username = re.sub(r'\s+', '.', username).lower()
    if domain:
        username = format_username(username, domain)
        validate_email(username)
    else:
        # if no domain, make sure that the username is a valid "local part" of an email address
        validate_email("%s@dimagi.com" % username)

    return username

def raw_username(username):
    """
    Strips the @domain.commcarehq.org from the username if it's there
    """
    sitewide_domain = settings.HQ_ACCOUNT_ROOT 
    username = username.lower()
    try:
        u, d = username.split("@")
    except Exception:
        return username
    if d.endswith('.' + sitewide_domain):
        return u
    else:
        return username

def user_id_to_username(user_id):
    if not user_id:
        return user_id
    elif user_id == "demo_user":
        return "demo_user"
    try:
        login = get_db().get(user_id)
    except ResourceNotFound:
        return None
    return raw_username(login['username']) if "username" in login else None

def django_user_from_couch_id(id):
    """
    From a couch id of a profile object, get the django user
    """
    # get the couch doc
    couch_rep = get_db().get(id)
    django_id = couch_rep["django_user"]["id"]
    return User.objects.get(id=django_id)

def doc_value_wrapper(doc_cls, value_cls):
    """
    Wrap both the doc and the value
    Code copied from couchdbkit.schema.base.QueryMixin.__view

    """
    #from corehq.apps.users.models import CouchUser
    def wrapper(row):

        data = row.get('value')
        docid = row.get('id')
        doc = row.get('doc')

        data['_id'] = docid
        if 'rev' in data:
            data['_rev'] = data.pop('rev')
        value_cls._allow_dynamic_properties = True
        doc_cls._allow_dynamic_properties = True
        value_inst = value_cls.wrap(data)
        doc_inst = doc_cls.wrap(doc)
        return doc_inst, value_inst
    return wrapper

def user_data_from_registration_form(xform):
    """
    Helper function for create_or_update_from_xform
    """
    user_data = {}
    if "user_data" in xform.form and "data" in xform.form["user_data"]:
        items = xform.form["user_data"]["data"]
        if not isinstance(items, list):
            items = [items]
        for item in items:
            user_data[item["@key"]] = item["#text"]
    return user_data