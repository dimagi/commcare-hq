from __future__ import absolute_import
from __future__ import unicode_literals
from collections import OrderedDict
from datetime import datetime, timedelta
import hashlib
import json

from django.conf import settings
from django.template import loader_tags, NodeList, TemplateSyntaxError
from django.template.base import Variable, VariableDoesNotExist, Token, TOKEN_TEXT
from django.template.loader import render_to_string
from django.utils.translation import ugettext as _
from django.http import QueryDict
from django import template
from django.urls import reverse
from django.utils.html import escape, format_html
from django.utils.safestring import mark_safe
from memoized import memoized
from django_prbac.utils import has_privilege

from dimagi.utils.make_uuid import random_hex
from corehq import privileges
from corehq.apps.domain.models import Domain
from corehq.util.quickcache import quickcache
from corehq.util.soft_assert import soft_assert
from dimagi.utils.web import json_handler
from corehq.apps.hqwebapp.models import MaintenanceAlert
from corehq.apps.hqwebapp.exceptions import AlreadyRenderedException
from corehq import toggles
import six


register = template.Library()


@register.filter
def JSON(obj):
    # json.dumps does not properly convert QueryDict array parameter to json
    if isinstance(obj, QueryDict):
        obj = dict(obj)
    try:
        return mark_safe(escape_script_tags(json.dumps(obj, default=json_handler)))
    except TypeError as e:
        msg = ("Unserializable data was sent to the `|JSON` template tag.  "
               "If DEBUG is off, Django will silently swallow this error.  "
               "{}".format(e.message))
        soft_assert(notify_admins=True)(False, msg)
        raise e


def escape_script_tags(unsafe_str):
    # seriously: http://stackoverflow.com/a/1068548/8207
    return unsafe_str.replace('</script>', '<" + "/script>')


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
        return datetime.strptime(date, '%m/%d/%Y').date() + span


@register.filter
def concat(str1, str2):
    """Concatenate two strings"""
    return "%s%s" % (str1, str2)

try:
    from resource_versions import resource_versions
except (ImportError, SyntaxError):
    resource_versions = {}


@register.filter
@register.simple_tag
def static(url):
    resource_url = url
    version = resource_versions.get(resource_url)
    url = settings.STATIC_CDN + settings.STATIC_URL + url
    is_less = url.endswith('.less')
    if version and not is_less:
        url += "?version=%s" % version
    return url


@register.simple_tag
def cachebuster(url):
    return resource_versions.get(url, "")


@quickcache(['couch_user.username'])
def _get_domain_list(couch_user):
    domains = Domain.active_for_user(couch_user)
    return [{
        'url': reverse('domain_homepage', args=[domain.name]),
        'name': domain.long_display_name(),
    } for domain in domains]


@register.simple_tag(takes_context=True)
def domains_for_user(context, request, selected_domain=None):
    """
    Generate pulldown menu for domains.
    Cache the entire string alongside the couch_user's doc_id that can get invalidated when
    the user doc updates via save.
    """

    domain_list = _get_domain_list(request.couch_user)
    ctxt = {
        'domain_list': sorted(domain_list, key=lambda domain: domain['name'].lower()),
        'current_domain': selected_domain,
        'can_publish_to_exchange': (
            selected_domain is not None and selected_domain != 'public' and
            request.couch_user and request.couch_user.can_edit_apps() and
            (request.couch_user.is_member_of(selected_domain) or
             request.couch_user.is_superuser)
        ),
    }
    return mark_safe(render_to_string('hqwebapp/includes/domain_list_dropdown.html', ctxt, request))


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
        new_dict = OrderedDict()
        key_list = list(value)
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


def _get_obj_from_name_or_instance(module, name_or_instance):
    if isinstance(name_or_instance, six.string_types):
        obj = getattr(module, name_or_instance)
    else:
        obj = name_or_instance
    return obj


def _toggle_enabled(module, request, toggle_or_toggle_name):
    toggle = _get_obj_from_name_or_instance(module, toggle_or_toggle_name)
    return toggle.enabled_for_request(request)


@register.filter
def toggle_enabled(request, toggle_or_toggle_name):
    import corehq.toggles
    return _toggle_enabled(corehq.toggles, request, toggle_or_toggle_name)


def _ui_notify_enabled(module, request, ui_notify_instance_or_name):
    ui_notify = _get_obj_from_name_or_instance(module, ui_notify_instance_or_name)
    return ui_notify.enabled(request)


@register.filter
def ui_notify_enabled(request, ui_notify_instance_or_name):
    import corehq.apps.notifications.ui_notify
    return _ui_notify_enabled(
        corehq.apps.notifications.ui_notify,
        request,
        ui_notify_instance_or_name
    )


@register.filter
def ui_notify_slug(ui_notify_instance_or_name):
    import corehq.apps.notifications.ui_notify
    ui_notify = _get_obj_from_name_or_instance(corehq.apps.notifications.ui_notify, ui_notify_instance_or_name)
    return ui_notify.slug


@register.filter
def toggle_tag_info(request, toggle_or_toggle_name):
    """Show Tag Information for feature flags / Toggles,
    and if not enabled, show where the UI would be.
    Useful for trying to find out if you have all the flags enabled in a
    particular location or whether a feature on prod is part of a particular
    flag. """
    if not toggles.SHOW_DEV_TOGGLE_INFO.enabled_for_request(request):
        return ""
    flag = _get_obj_from_name_or_instance(toggles, toggle_or_toggle_name)
    tag = flag.tag
    is_enabled = flag.enabled_for_request(request)
    return mark_safe("""<div class="label label-{css_class} label-flag{css_disabled}">{tag_name}: {description}{status}</div>""".format(
        css_class=tag.css_class,
        tag_name=tag.name,
        description=flag.label,
        status=" <strong>[DISABLED]</strong>" if not is_enabled else "",
        css_disabled=" label-flag-disabled" if not is_enabled else "",
    ))


@register.filter
def can_use_restore_as(request):
    if not hasattr(request, 'couch_user'):
        return False

    if request.couch_user.is_superuser:
        return True

    if toggles.LOGIN_AS_ALWAYS_OFF.enabled(request.domain):
        return False

    return (
        request.couch_user.can_edit_commcare_users() and
        has_privilege(request, privileges.LOGIN_AS)
    )


@register.simple_tag
def toggle_js_url(domain, username):
    return (
        '{url}?username={username}'
        '&cachebuster={toggles_cb}-{previews_cb}-{domain_cb}-{user_cb}'
    ).format(
        url=reverse('toggles_js', args=[domain]),
        username=username,
        domain_cb=toggle_js_domain_cachebuster(domain),
        user_cb=toggle_js_user_cachebuster(username),
        toggles_cb=toggles_cachebuster(),
        previews_cb=previews_cachebuster(),
    )


@quickcache(['domain'], timeout=30 * 24 * 60 * 60)
def toggle_js_domain_cachebuster(domain):
    # to get fresh cachebusters on the next deploy
    # change the date below (output from *nix `date` command)
    #   Mon Oct 31 10:30:09 EDT 2016
    return random_hex()[:3]


@quickcache(['username'], timeout=30 * 24 * 60 * 60)
def toggle_js_user_cachebuster(username):
    return random_hex()[:3]


def _get_py_filename(module):
    """
    return the full path to the .py file of a module
    (not the .pyc file)

    """
    return module.__file__.rstrip('c')


@memoized
def toggles_cachebuster():
    import corehq.toggles
    with open(_get_py_filename(corehq.toggles)) as f:
        return hashlib.sha1(f.read()).hexdigest()[:3]


@memoized
def previews_cachebuster():
    import corehq.feature_previews
    with open(_get_py_filename(corehq.feature_previews)) as f:
        return hashlib.sha1(f.read()).hexdigest()[:3]


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


@register.simple_tag
def chevron(value):
    """
    Displays a green up chevron if value > 0, and a red down chevron if value < 0
    """
    if value > 0:
        return format_html('<span class="fa fa-chevron-up" style="color: #006400;"></span>')
    elif value < 0:
        return format_html('<span class="fa fa-chevron-down" style="color: #8b0000;"> </span>')
    else:
        return ''


@register.simple_tag
def reverse_chevron(value):
    """
    Displays a red up chevron if value > 0, and a green down chevron if value < 0
    """
    if value > 0:
        return format_html('<span class="fa fa-chevron-up" style="color: #8b0000;"></span>')
    elif value < 0:
        return format_html('<span class="fa fa-chevron-down" style="color: #006400;"> </span>')
    else:
        return ''


@register.simple_tag
def maintenance_alert():
    try:
        alert = (MaintenanceAlert.objects
                 .filter(active=True)
                 .order_by('-modified'))[0]
    except IndexError:
        return ''
    else:
        return format_html(
            '<div class="alert alert-warning alert-maintenance" style="text-align: center; margin-bottom: 0;">{}</div>',
            mark_safe(alert.html),
        )


@register.simple_tag(takes_context=True)
def prelogin_url(context, urlname):
    """
    A prefix aware url tag replacement for prelogin URLs
    """
    if context.get('url_uses_prefix', False) and context.get('LANGUAGE_CODE', False):
        return reverse(urlname, args=[context['LANGUAGE_CODE']])
    else:
        return reverse(urlname)


@register.tag
def addtoblock(parser, token):
    try:
        tag_name, args = token.split_contents()
    except ValueError:
        raise template.TemplateSyntaxError("'addtoblock' tag requires a block_name.")

    nodelist = parser.parse(('endaddtoblock',))
    parser.delete_first_token()
    return AddToBlockNode(nodelist, args)


@register.tag(name='block')
def appending_block(parser, token):
    """
    this overrides {% block %} to include the combined contents of
    all {% addtoblock %} nodes
    """
    node = loader_tags.do_block(parser, token)
    node.__class__ = AppendingBlockNode
    return node


@register.tag(name='include')
def include_aware_block(parser, token):
    """
    this overrides {% include %} to keep track of whether the current template
    render context is in an include block
    """
    node = loader_tags.do_include(parser, token)
    node.__class__ = IncludeAwareNode
    return node


class AddToBlockNode(template.Node):

    def __init__(self, nodelist, block_name):
        self.nodelist = nodelist
        self.block_name = block_name

    def write(self, context, text):
        rendered_blocks = AppendingBlockNode.get_rendered_blocks_dict(context)
        if self.block_name in rendered_blocks:
            raise AlreadyRenderedException('Block {} already rendered. Cannot add new node'.format(self.block_name))
        request_blocks = self.get_addtoblock_contents_dict(context)
        if self.block_name not in request_blocks:
            request_blocks[self.block_name] = ''
        request_blocks[self.block_name] += text

    def render(self, context):
        output = self.nodelist.render(context)
        self.write(context, output)
        return ''

    @staticmethod
    def get_addtoblock_contents_dict(context):
        try:
            request_blocks = context.render_context._addtoblock_contents
        except AttributeError:
            request_blocks = context.render_context._addtoblock_contents = {}
        return request_blocks


class AppendingBlockNode(loader_tags.BlockNode):

    def render(self, context):
        super_result = super(AppendingBlockNode, self).render(context)
        if not IncludeAwareNode.get_include_count(context):
            request_blocks = AddToBlockNode.get_addtoblock_contents_dict(context)
            if self.name not in request_blocks:
                request_blocks[self.name] = ''

            contents = request_blocks.pop(self.name, '')
            rendered_blocks = self.get_rendered_blocks_dict(context)
            rendered_blocks.add(self.name)
            return super_result + contents
        else:
            return super_result

    @staticmethod
    def get_rendered_blocks_dict(context):
        try:
            rendered_blocks = context.render_context._rendered_blocks
        except AttributeError:
            rendered_blocks = context.render_context._rendered_blocks = set()
        return rendered_blocks


class IncludeAwareNode(loader_tags.IncludeNode):

    def render(self, context):
        include_count = IncludeAwareNode.get_include_count(context)
        include_count.append(True)
        super_result = super(IncludeAwareNode, self).render(context)
        include_count.pop()
        return super_result

    @staticmethod
    def get_include_count(context):
        try:
            include_count = context.render_context._includes
        except AttributeError:
            include_count = context.render_context._includes = []
        return include_count


@register.simple_tag(takes_context=True)
def url_replace(context, field, value):
    """Usage <a href="?{% url_replace 'since' restore_id %}">
    will replace the 'since' parameter in the url with <restore_id>
    note the presense of the '?' in the href value

    http://stackoverflow.com/a/16609591/2957657
    """
    params = context['request'].GET.copy()
    params[field] = value
    return params.urlencode()


@register.filter
def view_pdb(element):
    import ipdb; ipdb.set_trace()
    return element


@register.tag
def registerurl(parser, token):
    split_contents = token.split_contents()
    tag = split_contents[0]
    url_name = parse_literal(split_contents[1], parser, tag)
    expressions = [parser.compile_filter(arg) for arg in split_contents[2:]]

    class FakeNode(template.Node):
        # must mock token or error handling code will fail and not reveal real error
        token = Token(TOKEN_TEXT, '', (0, 0), 0)

        def render(self, context):
            args = [expression.resolve(context) for expression in expressions]
            url = reverse(url_name, args=args)
            return ("<div data-name=\"{}\" data-value={}></div>"
                    .format(url_name, json.dumps(url)))

    nodelist = NodeList([FakeNode()])

    return AddToBlockNode(nodelist, 'registered_urls')


@register.simple_tag
def html_attr(value):
    if not isinstance(value, six.string_types):
        value = JSON(value)
    return escape(value)


def _create_page_data(parser, token, node_slug):
    split_contents = token.split_contents()
    tag = split_contents[0]
    name = parse_literal(split_contents[1], parser, tag)
    value = parser.compile_filter(split_contents[2])

    class FakeNode(template.Node):
        def render(self, context):
            resolved = value.resolve(context)
            return ("<div data-name=\"{}\" data-value=\"{}\"></div>"
                    .format(name, html_attr(resolved)))

    nodelist = NodeList([FakeNode()])

    return AddToBlockNode(nodelist, node_slug)


@register.tag
def initial_page_data(parser, token):
    return _create_page_data(parser, token, 'initial_page_data')


@register.tag
def initial_analytics_data(parser, token):
    return _create_page_data(parser, token, 'initial_analytics_data')


@register.tag
def analytics_ab_test(parser, token):
    return _create_page_data(parser, token, 'analytics_ab_test')


@register.tag
def requirejs_main(parser, token):
    """
    Indicate that a page should be using RequireJS, by naming the
    JavaScript module to be used as the page's main entry point.

    The base template must have a `{% requirejs_main ... %}` tag before
    the `requirejs_main` variable is accessed anywhere in the template.
    The base template need not specify a value in its `{% requirejs_main %}`
    tag, allowing it to be extended by templates that may or may not
    use requirejs. In this case the `requirejs_main` template variable
    will have a value of `None` unless an extending template has a
    `{% requirejs_main "..." %}` with a value.
    """
    bits = token.contents.split(None, 1)
    if len(bits) == 1:
        tag_name = bits[0]
        value = None
    else:
        tag_name, value = bits
    if getattr(parser, "__saw_requirejs_main", False):
        raise TemplateSyntaxError(
            "multiple '%s' tags not allowed (%s)" % tuple(bits))
    parser.__saw_requirejs_main = True

    if value and (len(value) < 2 or value[0] not in '"\'' or value[0] != value[-1]):
        raise TemplateSyntaxError("bad '%s' argument: %s" % tuple(bits))

    # use a block to allow extension template to set requirejs_main for base
    return loader_tags.BlockNode("__" + tag_name, NodeList([
        RequireJSMainNode(tag_name, value and value[1:-1])
    ]))


class RequireJSMainNode(template.Node):

    def __init__(self, name, value):
        self.name = name
        self.value = value

    def __repr__(self):
        return "<RequireJSMain Node: %r>" % (self.value,)

    def render(self, context):
        if self.name not in context:
            # set name in block parent context
            context.dicts[-2][self.name] = self.value
        return ''


@register.inclusion_tag('hqwebapp/basic_errors.html')
def bootstrap_form_errors(form):
    return {'form': form}


@register.inclusion_tag('hqwebapp/includes/core_libraries.html', takes_context=True)
def javascript_libraries(context, **kwargs):
    return {
        'request': getattr(context, 'request', None),
        'underscore': kwargs.pop('underscore', False),
        'jquery_ui': kwargs.pop('jquery_ui', False),
        'ko': kwargs.pop('ko', False),
        'analytics': kwargs.pop('analytics', False),
        'hq': kwargs.pop('hq', False),
        'helpers': kwargs.pop('helpers', False),
    }
