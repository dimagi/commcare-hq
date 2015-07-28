from datetime import datetime, timedelta
import json
from django import template
from django.conf import settings
from django.core.urlresolvers import reverse
from django.template.base import Variable, VariableDoesNotExist
from django.template.loader import render_to_string
from django.utils.datastructures import SortedDict
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext as _
from django.http import QueryDict
from corehq.apps.domain.models import Domain
from corehq.util.soft_assert import soft_assert
from dimagi.utils.web import json_handler

import corehq.apps.style.utils as style_utils


register = template.Library()


@register.filter
def JSON(obj):
    # json.dumps does not properly convert QueryDict array parameter to json
    if isinstance(obj, QueryDict):
        obj = dict(obj)
    try:
        return mark_safe(json.dumps(obj, default=json_handler))
    except TypeError as e:
        msg = ("Unserializable data was sent to the `|JSON` template tag.  "
               "If DEBUG is off, Django will silently swallow this error.  "
               "{}".format(e.message))
        soft_assert(notify_admins=True)(False, msg)
        raise e


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


@register.simple_tag(takes_context=True)
def domains_for_user(context, request, selected_domain=None):
    """
    Generate pulldown menu for domains.
    Cache the entire string alongside the couch_user's doc_id that can get invalidated when
    the user doc updates via save.
    """
    domain_list = []
    if selected_domain != 'public':
        domain_list = Domain.active_for_user(request.couch_user)
    domain_list = [dict(
        url=reverse('domain_homepage', args=[d.name]),
        name=d.long_display_name()
    ) for d in domain_list]
    ctxt = {
        'is_public': selected_domain == 'public',
        'domain_list': domain_list,
        'current_domain': selected_domain,
        'DOMAIN_TYPE': context['DOMAIN_TYPE']
    }
    template = {
        style_utils.BOOTSTRAP_2: 'style/bootstrap2/partials/domain_list_dropdown.html',
        style_utils.BOOTSTRAP_3: 'style/bootstrap3/partials/domain_list_dropdown.html',
    }[style_utils.get_bootstrap_version()]
    return mark_safe(render_to_string(template, ctxt))


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


def _toggle_enabled(module, request, toggle_or_toggle_name):
    if isinstance(toggle_or_toggle_name, basestring):
        toggle = getattr(module, toggle_or_toggle_name)
    else:
        toggle = toggle_or_toggle_name
    return (
        (hasattr(request, 'user') and toggle.enabled(request.user.username)) or
        (hasattr(request, 'domain') and toggle.enabled(request.domain))
    )


@register.filter
def toggle_enabled(request, toggle_or_toggle_name):
    import corehq.toggles
    return _toggle_enabled(corehq.toggles, request, toggle_or_toggle_name)


@register.filter
def feature_preview_enabled(request, toggle_name):
    import corehq.feature_previews
    return _toggle_enabled(corehq.feature_previews, request, toggle_name)


def parse_literal(value, parser, tag):
    var = parser.compile_filter(value).var
    if isinstance(var, Variable):
        try:
            var = var.resolve({})
        except VariableDoesNotExist:
            raise template.TemplateSyntaxError(
                "'{}' tag expected literal value, got {}".format(tag, value))
    return var


@register.tag
def case(parser, token):
    """Hash-lookup branching tag

    Branch on value expression with optional default on no match::

        {% case place.value "first" %}
            You won first place!
        {% case "second" "third" %}
            Great job!
        {% else %}
            Practice is the way to success.
        {% endcase %}

    Each case must have at least one value. Case values must be literal,
    not expressions, and case values must be unique. An error is raised
    if more than one case exists with the same value.
    """
    args = token.split_contents()
    tag = args[0]
    if len(args) < 3:
        raise template.TemplateSyntaxError(
            "initial '{}' tag requires at least two arguments: a lookup "
            "expression and at least one value for the first case".format(tag))
    lookup_expr = parser.compile_filter(args[1])
    keys = [parse_literal(key, parser, tag) for key in args[2:]]
    branches = {}
    default = None
    while True:
        nodelist = parser.parse(("case", "else", "endcase"))
        for key in keys:
            if key in branches:
                raise template.TemplateSyntaxError(
                    "duplicate case not allowed: {!r}".format(key))
            branches[key] = nodelist
        token = parser.next_token()
        args = token.split_contents()
        tag = args[0]
        if tag != "case":
            break
        if len(args) < 2:
            raise template.TemplateSyntaxError(
                "inner 'case' tag requires at least one argument")
        keys = [parse_literal(key, parser, tag) for key in args[1:]]
    if len(args) > 1:
        raise template.TemplateSyntaxError(
            "'{}' tag does not accept arguments".format(tag))
    if tag == "else":
        default = parser.parse(("endcase",))
        token = parser.next_token()
        args = token.split_contents()
        tag = args[0]
        if len(args) > 1:
            raise template.TemplateSyntaxError(
                "'{}' tag does not accept arguments, got {}".format(tag))
    assert tag == "endcase", token.contents
    parser.delete_first_token()
    return CaseNode(lookup_expr, branches, default)


class CaseNode(template.Node):

    def __init__(self, lookup_expr, branches, default):
        self.lookup_expr = lookup_expr
        self.branches = branches
        self.default = default

    def render(self, context):
        key = self.lookup_expr.resolve(context)
        nodelist = self.branches.get(key, self.default)
        if nodelist is None:
            return ""
        return nodelist.render(context)


# https://djangosnippets.org/snippets/545/
@register.tag(name='captureas')
def do_captureas(parser, token):
    """
    Assign to a context variable from within a template
        {% captureas my_context_var %}<!-- anything -->{% endcaptureas %}
        <h1>Nice job capturing {{ my_context_var }}</h1>
    """
    try:
        tag_name, args = token.contents.split(None, 1)
    except ValueError:
        raise template.TemplateSyntaxError("'captureas' node requires a "
                                           "variable name.")
    nodelist = parser.parse(('endcaptureas',))
    parser.delete_first_token()
    return CaptureasNode(nodelist, args)


class CaptureasNode(template.Node):
    def __init__(self, nodelist, varname):
        self.nodelist = nodelist
        self.varname = varname

    def render(self, context):
        output = self.nodelist.render(context)
        context[self.varname] = output
        return ''
