import json
from collections import OrderedDict
from datetime import datetime, timedelta

from django import template
from django.conf import settings
from django.http import QueryDict
from django.template import NodeList, TemplateSyntaxError, loader_tags
from django.template.base import (
    Token,
    TokenType,
    Variable,
    VariableDoesNotExist,
)
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.html import conditional_escape, format_html
from django.utils.safestring import mark_safe
from django.utils.translation import gettext as _

from django_prbac.utils import has_privilege

from dimagi.utils.web import json_handler

from corehq import privileges
from corehq.apps.hqwebapp.exceptions import AlreadyRenderedException, TemplateTagJSONException
from corehq.apps.hqwebapp.models import Alert
from corehq.motech.utils import pformat_json
from corehq.util.quickcache import quickcache

register = template.Library()


@register.filter
def JSON(obj):
    # json.dumps does not properly convert QueryDict array parameter to json
    if isinstance(obj, QueryDict):
        obj = dict(obj)
    try:
        return escape_script_tags(json.dumps(obj, default=json_handler))
    except TypeError as e:
        msg = ("Unserializable data was sent to a template tag that expectes JSON. "
               "{}".format(str(e)))
        raise TemplateTagJSONException(msg)


def escape_script_tags(unsafe_str):
    # seriously: http://stackoverflow.com/a/1068548/8207
    return unsafe_str.replace('</script>', '<\\/script>')


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
def add_days(date, days=1):
    '''Return a date with some days added'''
    span = timedelta(days=days)
    try:
        return date + span
    except Exception:
        return datetime.strptime(date, '%m/%d/%Y').date() + span


try:
    from get_resource_versions import get_resource_versions
    resource_versions = get_resource_versions()
except (ImportError, SyntaxError):
    resource_versions = {}


@register.filter
def pp_json(data):
    """
    Pretty-print data as JSON
    """
    return pformat_json(data)


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
def get_domain_links_for_dropdown(couch_user):
    from corehq.apps.domain.views.base import get_domain_links
    return get_domain_links(couch_user)


@quickcache(['couch_user.username'])
def has_enterprise_links(couch_user):
    from corehq.apps.domain.views.base import get_enterprise_links
    return bool(get_enterprise_links(couch_user))


@register.simple_tag(takes_context=True)
def domains_for_user(context, request, selected_domain=None):
    """
    Generate pulldown menu for domains.
    Cache the entire string alongside the couch_user's doc_id that can get invalidated when
    the user doc updates via save.
    """
    domain_links = get_domain_links_for_dropdown(request.couch_user)

    # Enterprise permissions projects aren't in the dropdown, but show a hint they exist
    show_all_projects_link = has_enterprise_links(request.couch_user)

    # Too many domains and they won't all fit in the dropdown
    dropdown_limit = 20
    if len(domain_links) > dropdown_limit:
        show_all_projects_link = True
        domain_links = domain_links[:dropdown_limit]

    context = {
        'domain_links': domain_links,
        'show_all_projects_link': show_all_projects_link,
    }
    from corehq.apps.hqwebapp.utils.bootstrap import get_bootstrap_version
    return mark_safe(  # nosec: render_to_string should have already handled escaping
        render_to_string(
            f"hqwebapp/includes/{get_bootstrap_version()}/domain_list_dropdown.html",
            context, request
        )
    )


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
    if isinstance(name_or_instance, bytes):
        name_or_instance = name_or_instance.decode('utf-8')
    if isinstance(name_or_instance, str):
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
def can_use_restore_as(request):
    if not hasattr(request, 'couch_user'):
        return False

    if request.couch_user.is_superuser:
        return True

    domain = getattr(request, 'domain', None)

    return (
        request.couch_user.can_login_as(domain)
        and has_privilege(request, privileges.LOGIN_AS)
    )


@register.simple_tag
def css_label_class():
    from corehq.apps.hqwebapp.crispy import CSS_LABEL_CLASS, CSS_LABEL_CLASS_BOOTSTRAP5
    from corehq.apps.hqwebapp.utils.bootstrap import get_bootstrap_version, BOOTSTRAP_5
    if get_bootstrap_version() == BOOTSTRAP_5:
        return CSS_LABEL_CLASS_BOOTSTRAP5
    return CSS_LABEL_CLASS


@register.simple_tag
def css_field_class():
    from corehq.apps.hqwebapp.crispy import CSS_FIELD_CLASS, CSS_FIELD_CLASS_BOOTSTRAP5
    from corehq.apps.hqwebapp.utils.bootstrap import get_bootstrap_version, BOOTSTRAP_5
    if get_bootstrap_version() == BOOTSTRAP_5:
        return CSS_FIELD_CLASS_BOOTSTRAP5
    return CSS_FIELD_CLASS


@register.simple_tag
def css_action_class():
    from corehq.apps.hqwebapp.crispy import CSS_ACTION_CLASS, get_form_action_class
    from corehq.apps.hqwebapp.utils.bootstrap import get_bootstrap_version, BOOTSTRAP_5
    if get_bootstrap_version() == BOOTSTRAP_5:
        return get_form_action_class()
    return CSS_ACTION_CLASS


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
                f"'{tag}' tag does not accept arguments, got {len(args) - 1}")
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
def commcarehq_alerts(request):
    from corehq.apps.domain.auth import user_can_access_domain_specific_pages

    active_alerts = Alert.get_active_alerts()
    load_alerts_for_domain = None

    if hasattr(request, 'domain') and user_can_access_domain_specific_pages(request):
        load_alerts_for_domain = request.domain

    return [
        alert for alert in active_alerts
        if (not alert.domains
            or load_alerts_for_domain in alert.domains)
    ]


@register.simple_tag
def prelogin_url(urlname):
    """
    Fetches the correct dimagi.com url for a "prelogin" view.
    """
    urlname_to_url = {
        'go_to_pricing': 'https://dimagi.com/commcare/pricing/',
        'public_pricing': 'https://dimagi.com/commcare/pricing/',

    }
    return urlname_to_url.get(urlname, 'https://dimagi.com/commcare/')


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
            raise AlreadyRenderedException(f'Block {self.block_name} already rendered. Cannot add new node')
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
    import ipdb
    ipdb.sset_trace()
    return element


@register.tag
def registerurl(parser, token):
    split_contents = token.split_contents()
    tag = split_contents[0]
    url_name = parse_literal(split_contents[1], parser, tag)
    expressions = [parser.compile_filter(arg) for arg in split_contents[2:]]

    class FakeNode(template.Node):
        # must mock token or error handling code will fail and not reveal real error
        token = Token(TokenType.TEXT, '', (0, 0), 0)

        def render(self, context):
            args = [expression.resolve(context) for expression in expressions]
            url = reverse(url_name, args=args)
            return ("<div data-name=\"{}\" data-value={}></div>"
                    .format(url_name, json.dumps(url)))

    nodelist = NodeList([FakeNode()])

    return AddToBlockNode(nodelist, 'registered_urls')


@register.simple_tag
def trans_html_attr(value):
    if isinstance(value, bytes):
        value = value.decode('utf-8')
    if not isinstance(value, str):
        value = JSON(value)
    return conditional_escape(_(value))


@register.simple_tag
def html_attr(value):
    if isinstance(value, bytes):
        value = value.decode('utf-8')
    if not isinstance(value, str):
        value = JSON(value)
    return conditional_escape(value)


def _create_page_data(parser, token, node_slug):
    split_contents = token.split_contents()
    tag = split_contents[0]
    name = parse_literal(split_contents[1], parser, tag)
    value = parser.compile_filter(split_contents[2])

    class FakeNode(template.Node):
        # must mock token or error handling code will fail and not reveal real error
        token = Token(TokenType.TEXT, '', (0, 0), 0)

        def render(self, context):
            resolved = value.resolve(context)
            try:
                resolved_json = html_attr(resolved)
            except TemplateTagJSONException as e:
                msg = ("Error in initial page data key '{}'. "
                       "{}".format(name, str(e)))
                raise TemplateTagJSONException(msg)
            return ("<div data-name=\"{}\" data-value=\"{}\"></div>"
                    .format(name, resolved_json))

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
        'use_bootstrap5': kwargs.pop('use_bootstrap5', False),
    }


@register.simple_tag
def breadcrumbs(page, section, parents=None):
    """
    Generates breadcrumbs given a page, section,
    and (optional) list of parent pages.

    :param page: PageInfoContext or what is returned in
                 `current_page` of `BasePageView`'s `main_context`
    :param section: PageInfoContext or what is returned in
                    `section` of `BaseSectionPageView`'s `main_context`
    :param parents: list of PageInfoContext or what is returned in
                    `parent_pages` of `BasePageView`'s `main_context`
    :return:
    """

    from corehq.apps.hqwebapp.utils.bootstrap import get_bootstrap_version
    return render_to_string(f"hqwebapp/partials/{get_bootstrap_version()}/breadcrumbs.html", {
        'page': page,
        'section': section,
        'parents': parents or [],
    })


@register.filter
def request_has_privilege(request, privilege_name):
    from corehq.apps.accounting.utils import domain_has_privilege
    from corehq import privileges
    privilege = _get_obj_from_name_or_instance(privileges, privilege_name)
    return domain_has_privilege(request.domain, privilege)
