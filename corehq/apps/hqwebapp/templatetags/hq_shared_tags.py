from datetime import datetime, timedelta
import json
from django import template
from django.conf import settings
from django.core.urlresolvers import reverse
from django.template.loader import render_to_string
from django.utils.datastructures import SortedDict
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext as _
from corehq.apps.domain.models import Domain
from dimagi.utils.couch.cache import cache_core
from dimagi.utils.logging import notify_exception
from dimagi.utils.web import json_handler


register = template.Library()


@register.filter
def JSON(obj):
    return mark_safe(json.dumps(obj, default=json_handler))


@register.filter
def to_javascript_string(obj):
    # seriously: http://stackoverflow.com/a/1068548/8207
    return mark_safe(JSON(obj).replace('</script>', '<" + "/script>'))


@register.filter
def BOOL(obj):
    try:
        obj = obj.to_json()
    except AttributeError:
        pass

    return 'true' if obj else 'false'


@register.filter
def dict_lookup(dict, key):
    '''Get an item from a dictionary.'''
    return dict.get(key)
    

@register.filter
def array_lookup(array, index):
    '''Get an item from an array.'''
    if index < len(array):
        return array[index]
    

@register.simple_tag
def dict_as_query_string(dict, prefix=""):
    '''Convert a dictionary to a query string, minus the initial ?'''
    return "&".join(["%s%s=%s" % (prefix, key, value) for key, value in dict.items()])


@register.filter
def add_days(date, days=1):
    '''Return a date with some days added'''
    span = timedelta(days=days)
    try:
        return date + span
    except:
        return datetime.strptime(date,'%m/%d/%Y').date() + span 
    

@register.filter
def concat(str1, str2):
    """Concatenate two strings"""
    return "%s%s" % (str1, str2)

try:
    from resource_versions import resource_versions
except (ImportError, SyntaxError):
    resource_versions = {}


@register.simple_tag
def static(url):
    resource_url = url
    version = resource_versions.get(resource_url)
    url = settings.STATIC_URL + url
    if version:
        url += "?version=%s" % version
    return url


@register.simple_tag
def domains_for_user(request, selected_domain=None):
    """
    Generate pulldown menu for domains.
    Cache the entire string alongside the couch_user's doc_id that can get invalidated when
    the user doc updates via save.
    """


    lst = list()
    lst.append('<ul class="dropdown-menu nav-list dropdown-orange">')
    new_domain_url = reverse("registration_domain")
    if selected_domain == 'public':
        # viewing the public domain with a different db, so the user's domains can't readily be accessed.
        lst.append('<li><a href="%s">%s...</a></li>' % (reverse("domain_select"), _("Back to My Projects")))
        lst.append('<li class="divider"></li>')
    else:

        cached_domains = cache_core.get_cached_prop(request.couch_user.get_id, 'domain_list')
        if cached_domains:
            domain_list = [Domain.wrap(x) for x in cached_domains]
        else:
            try:
                domain_list = Domain.active_for_user(request.couch_user)
                cache_core.cache_doc_prop(request.couch_user.get_id, 'domain_list', [x.to_json() for x in domain_list])
            except Exception:
                if settings.DEBUG:
                    raise
                else:
                    domain_list = Domain.active_for_user(request.user)
                    notify_exception(request)

        if len(domain_list) > 0:
            lst.append('<li class="nav-header">%s</li>' % _('My Projects'))
            for domain in domain_list:
                default_url = reverse("domain_homepage", args=[domain.name])
                lst.append('<li><a href="%s">%s</a></li>' % (default_url, domain.long_display_name()))
        else:
            lst.append('<li class="nav-header">No Projects</li>')
    lst.append('<li class="divider"></li>')
    lst.append('<li><a href="%s">%s...</a></li>' % (new_domain_url, _('New Project')))
    lst.append('<li><a href="%s">%s...</a></li>' % (reverse("appstore"), _('CommCare Exchange')))
    lst.append("</ul>")

    domain_list_str = "".join(lst)
    return domain_list_str


@register.simple_tag
def list_my_domains(request):
    cached_val = cache_core.get_cached_prop(request.couch_user.get_id, 'list_my_domains')
    if cached_val:
        return cached_val.get('list_my_domains', "")

    domain_list = Domain.active_for_user(request.user)
    lst = list()
    lst.append('<ul class="nav nav-pills nav-stacked">')
    for domain in domain_list:
        default_url = reverse("domain_homepage", args=[domain.name])
        lst.append('<li><a href="%s">%s</a></li>' % (default_url, domain.display_name()))
    lst.append('</ul>')

    my_domain_list_str = "".join(lst)
    ret = {"list_my_domains": my_domain_list_str}
    cache_core.cache_doc_prop(request.couch_user.get_id, 'list_my_domains', ret)
    return my_domain_list_str


@register.simple_tag
def list_my_orgs(request):
    org_list = request.couch_user.get_organizations()
    lst = list()
    lst.append('<ul class="nav nav-pills nav-stacked">')
    for org in org_list:
        default_url = reverse("orgs_landing", args=[org.name])
        lst.append('<li><a href="%s">%s</a></li>' % (default_url, org.title))
    lst.append('</ul>')

    return "".join(lst)


@register.simple_tag
def commcare_user():
    return _(settings.COMMCARE_USER_TERM)


@register.simple_tag
def hq_web_user():
    return _(settings.WEB_USER_TERM)


@register.filter
def mod(value, arg):
    return value % arg


# This is taken from https://code.djangoproject.com/ticket/15583
@register.filter(name='sort')
def listsort(value):
    if isinstance(value, dict):
        new_dict = SortedDict()
        key_list = value.keys()
        key_list.sort()
        for key in key_list:
            new_dict[key] = value[key]
        return new_dict
    elif isinstance(value, list):
        new_list = list(value)
        new_list.sort()
        return new_list
    else:
        return value
listsort.is_safe = True


@register.filter(name='getattr')
def get_attribute(obj, arg):
    """ Get attribute from obj

    Usage: {{ couch_user|getattr:"full_name" }}
    """
    return getattr(obj, arg, None)


@register.filter
def pretty_doc_info(doc_info):
    return render_to_string('hqwebapp/pretty_doc_info.html', {
        'doc_info': doc_info,
    })


@register.filter
def toggle_enabled(request, toggle_name):
    import corehq.toggles
    toggle = getattr(corehq.toggles, toggle_name)
    return (
        (hasattr(request, 'user') and toggle.enabled(request.user.username)) or
        (hasattr(request, 'domain') and toggle.enabled(request.domain))
    )
