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

import corehq.apps.style.utils as style_utils


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
    is_less = url.endswith('.less')
    if version and not is_less:
        url += "?version=%s" % version
    return url


@register.simple_tag
def cachebuster(url):
    return resource_versions.get(url, "")


@register.simple_tag
def new_static(url, **kwargs):
    """Caching must explicitly be defined on tags with any of the extensions
    that could be compressed by django compressor. The static tag above will
    eventually turn into this tag.
    :param url:
    :param kwargs:
    :return:
    """
    can_be_compressed = url.endswith(('.less', '.css', '.js'))
    use_cache = kwargs.pop('cache', False)
    use_versions = not can_be_compressed or use_cache

    resource_url = url
    url = settings.STATIC_URL + url
    if use_versions:
        version = resource_versions.get(resource_url)
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
    domain_list = []
    if selected_domain != 'public':
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
    domain_list = [dict(
        url=reverse('domain_homepage', args=[d.name]),
        name=d.long_display_name()
    ) for d in domain_list]
    context = {
        'is_public': selected_domain == 'public',
        'domain_list': domain_list,
        'current_domain': selected_domain,
    }
    template = {
        style_utils.BOOTSTRAP_2: 'hqwebapp/partials/domain_list_dropdown.html',
        style_utils.BOOTSTRAP_3: 'style/includes/domain_list_dropdown.html',
    }[style_utils.bootstrap_version(request)]
    return mark_safe(render_to_string(template, context))


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
