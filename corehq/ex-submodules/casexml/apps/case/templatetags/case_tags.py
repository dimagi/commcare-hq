from functools import partial
import copy
import datetime
import numbers
import pytz
import json
import types

from django import template
from django.core.urlresolvers import reverse
from django.template.loader import render_to_string
from django.utils.translation import ugettext as _
from django.utils.safestring import mark_safe
from django.utils.html import escape

from corehq.apps.products.models import SQLProduct
from couchdbkit import ResourceNotFound
from corehq.apps.users.util import cached_owner_id_to_display

from corehq.form_processor.interfaces.dbaccessors import LedgerAccessors

register = template.Library()


DYNAMIC_CASE_PROPERTIES_COLUMNS = 4


class CaseDisplayWrapper(object):

    def __init__(self, case):
        self.case = case

    def actions(self):
        actions = self.case.to_json()['actions']
        return actions.reverse()

    def to_full_dict(self):
        """
        Include calculated properties that need to be available to the case
        details display by overriding this method.
        """
        json = self.case.to_json()
        json['status'] = _('Closed') if self.case.closed else _('Open')

        return json

    def get_display_config(self):
        return [
            {
                "layout": [
                    [
                        {
                            "expr": "name",
                            "name": _("Name"),
                        },
                        {
                            "expr": "opened_on",
                            "name": _("Opened On"),
                            "parse_date": True,
                            'is_phone_time': True,
                        },
                        {
                            "expr": "modified_on",
                            "name": _("Modified On"),
                            "parse_date": True,
                            "is_phone_time": True,
                        },
                        {
                            "expr": "closed_on",
                            "name": _("Closed On"),
                            "parse_date": True,
                            "is_phone_time": True,
                        },
                    ],
                    [
                        {
                            "expr": "type",
                            "name": _("Case Type"),
                            "format": '<code>{0}</code>',
                        },
                        {
                            "expr": "user_id",
                            "name": _("Last Submitter"),
                            "process": 'doc_info',
                        },
                        {
                            "expr": "owner_id",
                            "name": _("Owner"),
                            "process": 'doc_info',
                        },
                        {
                            "expr": "_id",
                            "name": _("Case ID"),
                        },
                    ],
                ],
            }
        ]

    def dynamic_properties(self):
        # pop seen properties off of remaining case properties
        dynamic_data = self.case.dynamic_case_properties()
        # hack - as of commcare 2.0, external id is basically a dynamic property
        # so also check and add it here
        if self.case.external_id:
            dynamic_data['external_id'] = self.case.external_id

        return dynamic_data

    @property
    def related_cases_columns(self):
        return [
            {
                'name': _('Status'),
                'expr': "status"
            },
            {
                'name': _('Case Type'),
                'expr': "type",
            },
            {
                'name': _('Owner'),
                'expr': lambda c: cached_owner_id_to_display(c.get('owner_id')),
            },
            {
                'name': _('Date Opened'),
                'expr': "opened_on",
                'parse_date': True,
                "is_phone_time": True,
            },
            {
                'name': _('Date Modified'),
                'expr': "modified_on",
                'parse_date': True,
                "is_phone_time": True,
            }
        ]

    @property
    def related_type_info(self):
        return None


class SupplyPointDisplayWrapper(CaseDisplayWrapper):

    def to_full_dict(self):
        from corehq.apps.locations.models import SQLLocation
        data = super(SupplyPointDisplayWrapper, self).to_full_dict()
        data.update({
            'location_type': None,
            'location_site_code': None,
            'location_parent_name': None,
        })
        try:
            location = SQLLocation.objects.get(location_id=self.case.location_id)
        except (SQLLocation.DoesNotExist, AttributeError):
            pass
        else:
            data['location_type'] = location.location_type_name
            data['location_site_code'] = location.site_code
            if location.parent:
                data['location_parent_name'] = location.parent.name

        return data

    def get_display_config(self):
        return [
            {
                "layout": [
                    [
                        {
                            "expr": "name",
                            "name": _("Name"),
                        },
                        {
                            "expr": "location_type",
                            "name": _("Type"),
                        },
                        {
                            "expr": "location_site_code",
                            "name": _("Code"),
                        },
                    ],
                    [
                        {
                            "expr": "location_parent_name",
                            "name": _("Parent Location"),
                        },
                        {
                            "expr": "owner_id",
                            "name": _("Location"),
                            "process": "doc_info",
                        },
                    ],
                ],
            }
        ]


def get_wrapped_case(case):
    from corehq.apps.commtrack import const
    wrapper_class = {
        const.SUPPLY_POINT_CASE_TYPE: SupplyPointDisplayWrapper,
    }.get(case.type, CaseDisplayWrapper)
    return wrapper_class(case)


def normalize_date(val):
    # Can't use isinstance since datetime is a subclass of date.
    if type(val) == datetime.date:
        return datetime.datetime.combine(val, datetime.time.min)

    return val


@register.simple_tag
def render_case(case, options):
    """
    Uses options since Django 1.3 doesn't seem to support templatetag kwargs.
    Change to kwargs when we're on a version of Django that does.
    """
    from corehq.apps.hqwebapp.templatetags.proptable_tags import get_tables_as_rows, get_default_definition
    wrapped_case = get_wrapped_case(case)
    timezone = options.get('timezone', pytz.utc)
    timezone = timezone.localize(datetime.datetime.utcnow()).tzinfo
    _get_tables_as_rows = partial(get_tables_as_rows, timezone=timezone)
    display = options.get('display') or wrapped_case.get_display_config()
    show_transaction_export = options.get('show_transaction_export') or False
    get_case_url = options['get_case_url']

    data = copy.deepcopy(wrapped_case.to_full_dict())

    default_properties = _get_tables_as_rows(data, display)

    dynamic_data = wrapped_case.dynamic_properties()

    for section in display:
        for row in section['layout']:
            for item in row:
                dynamic_data.pop(item.get("expr"), None)

    if dynamic_data:
        dynamic_keys = sorted(dynamic_data.keys())
        definition = get_default_definition(
            dynamic_keys, num_columns=DYNAMIC_CASE_PROPERTIES_COLUMNS)

        dynamic_properties = _get_tables_as_rows(dynamic_data, definition)
    else:
        dynamic_properties = None

    the_time_is_now = datetime.datetime.utcnow()
    tz_offset_ms = int(timezone.utcoffset(the_time_is_now).total_seconds()) * 1000
    tz_abbrev = timezone.localize(the_time_is_now).tzname()

    # ledgers
    def _product_name(product_id):
        try:
            return SQLProduct.objects.get(product_id=product_id).name
        except SQLProduct.DoesNotExist:
            return (_('Unknown Product ("{}")').format(product_id))

    ledger_map = LedgerAccessors(case.domain).get_case_ledger_state(case.case_id, ensure_form_id=True)
    for section, product_map in ledger_map.items():
        product_tuples = sorted(
            (_product_name(product_id), product_map[product_id]) for product_id in product_map
        )
        ledger_map[section] = product_tuples

    return render_to_string("case/partials/single_case.html", {
        "default_properties": default_properties,
        "default_properties_options": {
            "style": "table"
        },
        "dynamic_properties": dynamic_properties,
        "dynamic_properties_options": {
            "style": "table"
        },
        "case": wrapped_case.case,
        "case_actions": mark_safe(json.dumps(wrapped_case.actions())),
        "timezone": timezone,
        "tz_abbrev": tz_abbrev,
        "case_hierarchy_options": {
            "show_view_buttons": True,
            "get_case_url": get_case_url,
            "timezone": timezone
        },
        "ledgers": ledger_map,
        "timezone_offset": tz_offset_ms,
        "show_transaction_export": show_transaction_export,
        "xform_api_url": reverse('single_case_forms', args=[case.domain, case.case_id]),
    })


def get_inverse(val):
    if isinstance(val, (datetime.datetime, datetime.date)):
        return datetime.datetime.max - val
    elif isinstance(val, numbers.Number):
        return 10 ** 20
    elif isinstance(val, (types.NoneType, bool)):
        return not val
    else:
        raise Exception("%r has uninversable type: %s" % (val, type(val)))


def sortkey(child, type_info=None):
    """Return sortkey based on sort order defined in type_info, or use default
    based on open/closed and opened_on/closed_on dates.
    """
    type_info = type_info or {}
    case = child['case']
    if case.closed:
        key = [1]
        try:
            for attr, direction in type_info[case.type]['closed_sortkeys']:
                val = normalize_date(getattr(case, attr))
                if direction.lower() == 'desc':
                    val = get_inverse(val)
                key.append(val)
        except KeyError:
            key.append(datetime.datetime.max - case.closed_on)
    else:
        key = [0]
        try:
            for attr, direction in type_info[case.type]['open_sortkeys']:
                val = normalize_date(getattr(case, attr))
                if direction.lower() == 'desc':
                    val = get_inverse(val)
                key.append(val)
        except KeyError:
            key.append(case.opened_on or datetime.datetime.min)
    return key


def get_session_data(case, current_case, type_info):
    # this logic should ideally be implemented in subclasses of
    # CommCareCase
    if type_info and case.type in type_info:
        attr = type_info[case.type]['case_id_attr']
        return {
            attr: case.case_id,
            'case_id': current_case.case_id
        }
    else:
        return {
            'case_id': case.case_id
        }


TREETABLE_INDENT_PX = 19


def process_case_hierarchy(case_output, get_case_url, type_info):
    current_case = case_output['case']
    submit_url_root = reverse('receiver_post', args=[current_case.domain])
    form_url_root = reverse('cloudcare_main', args=[current_case.domain, ''])

    def process_output(case_output, depth=0):
        for c in case_output['child_cases']:
            process_output(c, depth=depth + 1)

        case = case_output['case']
        common_data = {
            'indent_px': depth * TREETABLE_INDENT_PX,
            'submit_url_root': submit_url_root,
            'form_url_root': form_url_root,
            'view_url': get_case_url(case.case_id),
            'session_data': get_session_data(case, current_case, type_info)
        }
        data = type_info.get(case.type, {})
        if 'description_property' in data:
            data['description'] = getattr(
                    case, data['description_property'], None)
        if 'edit_session_data' in data:
            data['session_data'].update(data['edit_session_data'])
        data.update(common_data)

        case.edit_data = data

        if 'child_type' in data and not case.closed:
            child_type = data['child_type']
            child_data = type_info.get(child_type, {})
            child_data.update(common_data)
            child_data.update({
                "link_text": _("Add %(case_type)s") % {
                    'case_type': child_data.get('type_name', child_type)
                },
                "parent_node_id": case.case_id,
            })

            if 'create_session_data' in child_data:
                child_data['session_data'].update(child_data['create_session_data'])
            case.add_child_data = child_data

    process_output(case_output)


def get_case_hierarchy(case, type_info):
    def get_children(case, referenced_type=None, seen=None):
        seen = seen or set()

        ignore_types = type_info.get(case.type, {}).get("ignore_relationship_types", [])
        if referenced_type and referenced_type in ignore_types:
            return None

        seen.add(case.case_id)
        children = [
            get_children(i.referenced_case, i.referenced_type, seen) for i in case.reverse_indices
            if i.referenced_id not in seen
        ]

        children = [c for c in children if c is not None]

        # non-first-level descendants
        descendant_types = []
        for c in children:
            descendant_types.extend(c['descendant_types'])
        descendant_types = list(set(descendant_types))

        children = sorted(children, key=partial(sortkey, type_info=type_info))
       
        # set parent_case_id used by flat display
        for c in children:
            if not hasattr(c['case'], 'treetable_parent_node_id'):
                c['case'].treetable_parent_node_id = case.case_id
      
        child_cases = []
        for c in children:
            child_cases.extend(c['case_list'])

        return {
            'case': case,
            'child_cases': children,
            'descendant_types': list(set(descendant_types + [c['case'].type for c in children])),
            'case_list': [case] + child_cases
        }

    return get_children(case)


def get_flat_descendant_case_list(case, get_case_url, type_info=None):
    type_info = type_info or {}
    hierarchy = get_case_hierarchy(case, type_info)
    process_case_hierarchy(hierarchy, get_case_url, type_info)
    return hierarchy['case_list']


@register.simple_tag
def render_case_hierarchy(case, options):
    from corehq.apps.hqwebapp.templatetags.proptable_tags import get_display_data

    wrapped_case = get_wrapped_case(case)
    get_case_url = options.get('get_case_url')
    timezone = options.get('timezone', pytz.utc)
    columns = options.get('columns') or wrapped_case.related_cases_columns
    show_view_buttons = options.get('show_view_buttons', True)
    type_info = options.get('related_type_info', wrapped_case.related_type_info)

    descendent_case_list = get_flat_descendant_case_list(
        case, get_case_url, type_info=type_info
    )

    parent_cases = []
    if case.indices:
        # has parent case(s)
        # todo: handle duplicates in ancestor path (bubbling up of parent-child
        # relationships)
        for idx in case.indices:
            try:
                parent_cases.append(idx.referenced_case)
            except ResourceNotFound:
                parent_cases.append(None)
        for parent_case in parent_cases:
            if parent_case:
                parent_case.edit_data = {
                    'view_url': get_case_url(parent_case.case_id)
                }
                last_parent_id = parent_case.case_id
            else:
                last_parent_id = None

        for c in descendent_case_list:
            if not getattr(c, 'treetable_parent_node_id', None) and last_parent_id:
                c.treetable_parent_node_id = last_parent_id

    case_list = parent_cases + descendent_case_list

    for c in case_list:
        if not c:
            continue
        c.columns = []
        case_dict = get_wrapped_case(c).to_full_dict()
        for column in columns:
            c.columns.append(get_display_data(
                case_dict, column, timezone=timezone))

    return render_to_string("case/partials/case_hierarchy.html", {
        'current_case': case,
        'domain': case.domain,
        'case_list': case_list,
        'columns': columns,
        'num_columns': len(columns) + 1,
        'show_view_buttons': show_view_buttons,
    })

    
@register.simple_tag
def case_inline_display(case):
    """
    Given a case id, make a best effort at displaying it.
    """
    if case:
        if case.opened_on:
            ret = "%s (%s: %s)" % (case.name, _("Opened"), case.opened_on.date())
        else:
            ret = case.name
    else:
        ret = _("Empty Case")

    return escape(ret)
