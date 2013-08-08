from datetime import datetime, timedelta
import json
from django import template
from django.conf import settings
from django.core.urlresolvers import reverse
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext as _
from corehq.apps.domain.models import Domain
from dimagi.utils.logging import notify_exception
from dimagi.utils.web import json_handler


register = template.Library()

@register.filter
def JSON(obj):
    return mark_safe(json.dumps(obj, default=json_handler))

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
def less(path, media=None):

    if not settings.DEBUG:
        path = path.replace('/less/', '/css/')
        if path.endswith('.less'):
            path = path[:-3] + "css"

    data = {
        'media': media if media is not None else '',
        'href': static(path),
        'rel': 'stylesheet/less' if settings.DEBUG else 'stylesheet'
    }

    fmt = "<link rel='%(rel)s' type='text/css' href='%(href)s' %(media)s/>"
    return mark_safe(fmt % data)


@register.simple_tag
def get_report_analytics_tag(request):
    # todo: change this to takes_context=True and check the active_tab context
    # variable to see exactly whether the reports tab is active
    if 'reports' in request.path_info:
        try:
            report_name = request.path_info.split('reports/')[1][:-1].replace('_', ' ')
        except IndexError:
            return ''

        return "_gaq.push(['_setCustomVar', 2, 'report', '%s', 3]);\n_gaq.push(['_trackEvent', 'Viewed Report', '%s']);" % (report_name, report_name)
    return ''

@register.simple_tag
def domains_for_user(request, selected_domain=None):
    lst = list()
    lst.append('<ul class="dropdown-menu nav-list dropdown-orange">')
    new_domain_url = reverse("registration_domain")
    if selected_domain == 'public':
        # viewing the public domain with a different db, so the user's domains can't readily be accessed.
        lst.append('<li><a href="%s">Back to My Projects...</a></li>' % reverse("domain_select"))
        lst.append('<li class="divider"></li>')
    else:
        try:
            domain_list = Domain.active_for_user(request.couch_user)
        except Exception:
            if settings.DEBUG:
                raise
            else:
                domain_list = Domain.active_for_user(request.user)
                notify_exception(request)

        if len(domain_list) > 0:
            lst.append('<li class="nav-header">My Projects</li>')
            for domain in domain_list:
                default_url = reverse("domain_homepage", args=[domain.name])
                lst.append('<li><a href="%s">%s</a></li>' % (default_url, domain.long_display_name()))
        else:
            lst.append('<li class="nav-header">No Projects</li>')
    lst.append('<li class="divider"></li>')
    lst.append('<li><a href="%s">New Project...</a></li>' % new_domain_url)
    lst.append('<li><a href="%s">CommCare Exchange...</a></li>' % reverse("appstore"))
    lst.append("</ul>")

    return "".join(lst)

@register.simple_tag
def list_my_domains(request):
    domain_list = Domain.active_for_user(request.user)
    lst = list()
    lst.append('<ul class="nav nav-pills nav-stacked">')
    for domain in domain_list:
        default_url = reverse("domain_homepage", args=[domain.name])
        lst.append('<li><a href="%s">%s</a></li>' % (default_url, domain.display_name()))
    lst.append('</ul>')

    return "".join(lst)

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


# This is taken verbatim from https://code.djangoproject.com/ticket/15583
@register.filter(name='sort')
def listsort(value):
    if isinstance(value,dict):
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
