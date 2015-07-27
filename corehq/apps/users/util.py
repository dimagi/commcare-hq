import re

from django.conf import settings
from django.contrib.auth.models import User
from django.utils import html, safestring

from couchdbkit.resource import ResourceNotFound
from corehq import privileges

from dimagi.utils.couch.database import get_db
from django.core.cache import cache
from django_prbac.exceptions import PermissionDenied
from django_prbac.utils import has_privilege


WEIRD_USER_IDS = [
    'commtrack-system',    # internal HQ/commtrack system forms
    'demo_user',           # demo mode
    'demo_user_group_id',  # demo mode with case sharing enabled
]


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
    from corehq.apps.users.models import CouchUser
    if not user_id:
        return user_id
    elif user_id == "demo_user":
        return "demo_user"
    try:
        login = CouchUser.get_db().get(user_id)
    except ResourceNotFound:
        return None
    return raw_username(login['username']) if "username" in login else None


def cached_user_id_to_username(user_id):
    if not user_id:
        return None

    key = 'user_id_username_cache_{id}'.format(id=user_id)
    ret = cache.get(key)
    if ret:
        return ret
    else:
        ret = user_id_to_username(user_id)
        cache.set(key, ret)
        return ret


def cached_owner_id_to_display(owner_id):
    from corehq.apps.users.cases import get_wrapped_owner
    from corehq.apps.users.models import CouchUser
    key = 'owner_id_to_display_cache_{id}'.format(id=owner_id)
    ret = cache.get(key)
    if ret:
        return ret
    owner = get_wrapped_owner(owner_id)
    if owner is None:
        return None
    else:
        ret = raw_username(owner.username) if isinstance(owner, CouchUser) else owner.name
        cache.set(key, ret)
        return ret


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


def can_add_extra_mobile_workers(request):
    from corehq.apps.users.models import CommCareUser
    from corehq.apps.accounting.models import BillingAccount
    num_web_users = CommCareUser.total_by_domain(request.domain)
    user_limit = request.plan.user_limit
    if user_limit == -1 or num_web_users < user_limit:
        return True
    if not has_privilege(request, privileges.ALLOW_EXCESS_USERS):
        account = BillingAccount.get_account_by_domain(request.domain)
        if account is None or account.date_confirmed_extra_charges is None:
            return False
    return True


def smart_query_string(query):
    """
    If query does not use the ES query string syntax,
    default to doing an infix search for each term.
    returns (is_simple, query)
    """
    special_chars = ['&&', '||', '!', '(', ')', '{', '}', '[', ']', '^', '"',
                     '~', '*', '?', ':', '\\', '/']
    for char in special_chars:
        if char in query:
            return False, query
    r = re.compile(r'\w+')
    tokens = r.findall(query)
    return True, "*{}*".format("* *".join(tokens))


def user_display_string(username, first_name="", last_name=""):
    full_name = u"{} {}".format(first_name or u'', last_name or u'').strip()

    def parts():
        yield u'%s' % html.escape(raw_username(username))
        if full_name:
            yield u' "%s"' % html.escape(full_name)

    return safestring.mark_safe(''.join(parts()))
