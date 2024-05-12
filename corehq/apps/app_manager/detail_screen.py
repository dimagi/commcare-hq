import re

from corehq.apps.app_manager import id_strings
from corehq.apps.app_manager.suite_xml import const
from corehq.apps.app_manager.suite_xml import xml_models as sx
from corehq.apps.app_manager.xpath import (
    CaseXPath,
    CommCareSession,
    IndicatorXpath,
    LedgerdbXpath,
    LocationXpath,
    UsercaseXPath,
    XPath,
)
from corehq.apps.hqmedia.models import CommCareMultimedia

CASE_PROPERTY_MAP = {
    # IMPORTANT: if you edit this you probably want to also edit
    # the corresponding map in cloudcare
    # (corehq/apps/cloudcare/static/cloudcare/js/backbone/cases.js)
    'external-id': 'external_id',
    'date-opened': 'date_opened',
    'status': '@status',
    'name': 'case_name',
    'owner_id': '@owner_id',
}


def get_column_generator(app, module, detail, column, sort_element=None,
                         order=None, detail_type=None, parent_tab_nodeset=None, style=None,
                         entries_helper=None):
    cls = get_class_for_format(column.format)  # cls will be FormattedDetailColumn or a subclass of it
    return cls(app, module, detail, column, sort_element, order,
               detail_type=detail_type, parent_tab_nodeset=parent_tab_nodeset, style=style,
               entries_helper=entries_helper)


def get_class_for_format(slug):
    return get_class_for_format._format_map.get(slug, FormattedDetailColumn)


get_class_for_format._format_map = {}


class register_format_type(object):

    def __init__(self, slug):
        self.slug = slug

    def __call__(self, klass):
        get_class_for_format._format_map[self.slug] = klass
        return klass


def get_column_xpath_generator(app, module, detail, column):
    cls = get_class_for_type(column.field_type)  # cls will be BaseXpathGenerator or a subclass
    return cls(app, module, detail, column)


def get_class_for_type(slug):
    return get_class_for_type._type_map.get(slug, BaseXpathGenerator)


get_class_for_type._type_map = {}


class register_type_processor(object):

    def __init__(self, slug):
        self.slug = slug

    def __call__(self, klass):
        get_class_for_type._type_map[self.slug] = klass
        return klass


class BaseXpathGenerator(object):

    def __init__(self, app, module, detail, column):
        self.app = app
        self.module = module
        self.detail = detail
        self.column = column
        self.id_strings = id_strings

    @property
    def xpath(self):
        return self.column.field


class FormattedDetailColumn(object):

    header_width = None
    template_width = None
    template_form = None

    SORT_TYPE = 'string'

    def __init__(self, app, module, detail, column, sort_element=None,
                 order=None, detail_type=None, parent_tab_nodeset=None, style=None,
                 entries_helper=None):
        self.app = app
        self.module = module
        self.detail = detail
        self.detail_type = detail_type
        self.column = column
        self.sort_element = sort_element
        self.order = order
        self.id_strings = id_strings
        self.parent_tab_nodeset = parent_tab_nodeset
        self.style = style
        self.entries_helper = entries_helper

    def has_sort_node_for_nodeset_column(self):
        return self.parent_tab_nodeset and self.detail.sort_nodeset_columns_for_detail()

    @property
    def locale_id(self):
        return self.id_strings.detail_column_header_locale(
            self.module, self.detail_type, self.column,
        )

    @property
    def header(self):
        header = sx.Header(
            text=sx.Text(locale_id=self.locale_id),
            width=self.header_width
        )
        return header

    @property
    def variables(self):
        variables = {}
        if re.search(r'\$lang', self.xpath_function):
            variables['lang'] = self.id_strings.current_language()
        return variables

    @property
    def template(self):
        template = sx.Template(
            text=sx.Text(xpath_function=self.xpath_function),
            form=self.template_form,
            width=self.template_width,
        )

        if self.column.useXpathExpression:
            xpath = sx.CalculatedPropertyXPath(function=self.xpath)
            if re.search(r'\$lang', self.xpath):
                xpath.variables.node.append(
                    sx.CalculatedPropertyXPathVariable(
                        name='lang',
                        locale_id=self.id_strings.current_language()
                    ).node
                )
            xpath_variable = sx.XPathVariable(name='calculated_property', xpath=xpath)
            template.text.xpath.variables.node.append(xpath_variable.node)

        if self.variables:
            for key, value in sorted(self.variables.items()):
                template.text.xpath.variables.node.append(
                    sx.XPathVariable(name=key, locale_id=value).node
                )

        return template

    @property
    def sort_node(self):
        if not (self.app.enable_multi_sort
                and (self.detail.display == 'short' or self.has_sort_node_for_nodeset_column())
                ):
            return

        sort = None

        if self.sort_xpath_function:
            if self.sort_element and self.sort_element.type == 'index':
                sort_type = self.sort_element.type
            else:
                sort_type = self.SORT_TYPE

            sort = sx.Sort(
                text=sx.Text(xpath_function=self.sort_xpath_function),
                type=sort_type,
            )

            if self.column.useXpathExpression:
                xpath = sx.CalculatedPropertyXPath(function=self.xpath)
                if re.search(r'\$lang', self.xpath):
                    xpath.variables.node.append(
                        sx.CalculatedPropertyXPathVariable(
                            name='lang',
                            locale_id=self.id_strings.current_language()
                        ).node
                    )
                xpath_variable = sx.XPathVariable(name='calculated_property', xpath=xpath)
                sort.text.xpath.variables.node.append(xpath_variable.node)

        if self.sort_element:
            if not sort:
                sort_type = {
                    'date': 'string',
                    'plain': 'string',
                    'distance': 'double'
                }.get(self.sort_element.type, self.sort_element.type)

                sort_calculation = self.sort_element.sort_calculation
                if sort_calculation:
                    sort_xpath = sort_calculation
                else:
                    sort_xpath = self.xpath_function

                sort = sx.Sort(
                    text=sx.Text(xpath_function=sort_xpath),
                    type=sort_type,
                )
                if not sort_calculation and self.column.useXpathExpression:
                    xpath = sx.CalculatedPropertyXPath(function=self.xpath)
                    if re.search(r'\$lang', self.xpath):
                        xpath.variables.node.append(
                            sx.CalculatedPropertyXPathVariable(
                                name='lang', locale_id=self.id_strings.current_language()
                            ).node
                        )
                    xpath_variable = sx.XPathVariable(name='calculated_property', xpath=xpath)
                    sort.text.xpath.variables.node.append(xpath_variable.node)

            if self.sort_element.type == 'distance':
                sort.text.xpath_function = self.evaluate_template(Distance.SORT_XPATH_FUNCTION)

            sort.order = self.order
            sort.direction = self.sort_element.direction
            sort.blanks = self.sort_element.blanks

            # Flag field as index by making order "-2"
            # this is for the CACHE_AND_INDEX toggle
            # (I know, I know, it's hacky - blame Clayton)
            if sort.type == 'index':
                sort.type = 'string'
                sort.order = -2

        return sort

    @property
    def xpath(self):
        if self.column.useXpathExpression:
            return self.column.field
        return get_column_xpath_generator(self.app, self.module, self.detail,
                                          self.column).xpath

    XPATH_FUNCTION = "{xpath}"

    def evaluate_template(self, template):
        if template:
            return template.format(
                xpath='$calculated_property' if self.column.useXpathExpression else self.xpath,
                app=self.app,
                module=self.module,
                detail=self.detail,
                column=self.column
            )

    @property
    def xpath_function(self):
        return self.evaluate_template(self.XPATH_FUNCTION)

    @property
    def hidden_header(self):
        return sx.Header(
            text=sx.Text(),
            width=0,
        )

    @property
    def hidden_template(self):
        return sx.Template(
            text=sx.Text(xpath_function=self.sort_xpath_function),
            width=0,
        )

    SORT_XPATH_FUNCTION = None

    @property
    def sort_xpath_function(self):
        return self.evaluate_template(self.SORT_XPATH_FUNCTION)

    @property
    def action(self):
        return None

    @property
    def alt_text(self):
        return None

    @property
    def fields(self):
        print_id = None
        if self.detail.print_template:
            print_id = self.column.field

        if self.app.enable_multi_sort:
            yield sx.Field(
                style=self.style,
                header=self.header,
                template=self.template,
                sort_node=self.sort_node,
                print_id=print_id,
                endpoint_action=self.action,
                alt_text=self.alt_text,
            )
        elif self.sort_xpath_function and self.detail.display == 'short':
            yield sx.Field(
                style=self.style,
                header=self.header,
                template=self.hidden_template,
                print_id=print_id,
            )
            yield sx.Field(
                style=self.style,
                header=self.hidden_header,
                template=self.template,
                print_id=print_id,
            )
        else:
            yield sx.Field(
                style=self.style,
                header=self.header,
                template=self.template,
                print_id=print_id,
            )


class HideShortHeaderColumn(FormattedDetailColumn):

    @property
    def header(self):
        if self.detail.display == 'short' or self.has_sort_node_for_nodeset_column():
            header = sx.Header(
                text=sx.Text(),
                width=self.template_width
            )
        else:
            header = super(HideShortHeaderColumn, self).header
        return header


class HideShortColumn(HideShortHeaderColumn):

    @property
    def template_width(self):
        if self.detail.display == 'short' or self.has_sort_node_for_nodeset_column():
            return 0


@register_format_type('plain')
class Plain(FormattedDetailColumn):
    pass


@register_format_type('date')
class Date(FormattedDetailColumn):
    XPATH_FUNCTION = "if({xpath} = '', '', format-date(date({xpath}), '{column.date_format}'))"
    SORT_XPATH_FUNCTION = "{xpath}"


@register_format_type('time-ago')
class TimeAgo(FormattedDetailColumn):
    XPATH_FUNCTION = "if({xpath} = '', '', string(int((today() - date({xpath})) div {column.time_ago_interval})))"
    SORT_XPATH_FUNCTION = "{xpath}"


@register_format_type('distance')
class Distance(FormattedDetailColumn):
    XPATH_FUNCTION = \
        "if(here() = '' or {xpath} = '', '', concat(round(distance({xpath}, here()) div 100) div 10, ' km'))"
    SORT_XPATH_FUNCTION = "if({xpath} = '', 2147483647, round(distance({xpath}, here())))"
    SORT_TYPE = 'double'


@register_format_type('phone')
class Phone(FormattedDetailColumn):

    @property
    def template_form(self):
        if self.detail.display == 'long':
            return 'phone'


@register_format_type('enum')
class Enum(FormattedDetailColumn):
    def _make_xpath(self, type):
        return sx.XPathEnum.build(
            enum=self.column.enum,
            format=self.column.format,
            type=type,
            template=self._xpath_template(type),
            get_template_context=self._xpath_template_context(type),
            get_value=lambda key: self.id_strings.detail_column_enum_variable(self.module, self.detail_type,
                                                                              self.column, key))

    def _xpath_template(self, type):
        if type == 'sort':
            return "if(selected({xpath}, '{key}'), {i}, "
        if type == 'display':
            return "if(selected({xpath}, '{key}'), ${key_as_var}, ''), "
        raise ValueError('type must be in sort, display')

    def _xpath_template_context(self, type):
        return lambda item, i: {
            'key': item.key,
            'key_as_var': item.key_as_variable,
            'xpath': '$calculated_property' if self.column.useXpathExpression else self.xpath,
            'i': i,
        }

    @property
    def xpath_function(self):
        return self._make_xpath('display').function

    @property
    def sort_xpath_function(self):
        return self._make_xpath('sort').function

    @property
    def variables(self):
        return {v.name: v.value for v in self._make_xpath('display').variables}


@register_format_type('conditional-enum')
class ConditionalEnum(Enum):
    @property
    def sort_node(self):
        node = super(ConditionalEnum, self).sort_node
        if node:
            variables = self.variables
            for key in variables:
                node.text.xpath.node.append(
                    sx.XPathVariable(name=key, locale_id=variables[key]).node
                )
        return node

    def _xpath_template(self, type):
        return "if({key_as_condition}, {key_as_var_name}"

    def _xpath_template_context(self, type):
        return lambda item, i: {
            'key_as_condition': item.key_as_condition(self.xpath),
            'key_as_var_name': item.ref_to_key_variable(i, 'display')
        }


@register_format_type('enum-image')
class EnumImage(Enum):
    template_form = 'image'

    @property
    def header_width(self):
        return self.template_width

    @property
    def template_width(self):
        '''
        Set column width to accommodate widest image.
        '''
        width = 0
        if self.app.enable_case_list_icon_dynamic_width:
            for i, item in enumerate(self.column.enum):
                for path in item.value.values():
                    map_item = self.app.multimedia_map[path]
                    if map_item is not None:
                        image = CommCareMultimedia.get(map_item.multimedia_id)
                        if image is not None:
                            for media in image.aux_media:
                                width = max(width, media.media_meta['size']['width'])
        if width == 0:
            return '13%'
        return str(width)

    @property
    def action(self):
        if self.column.endpoint_action_id and self.app.supports_detail_field_action:
            return sx.EndpointAction(endpoint_id=self.column.endpoint_action_id, background="true")

    def _make_alt_text(self, type):
        return sx.XPathEnum.build(
            enum=self.column.enum,
            format=self.column.format,
            type=type,
            template=self._xpath_template(type),
            get_template_context=self._xpath_template_context(type),
            get_value=lambda key: self.id_strings.detail_column_alt_text_variable(self.module, self.detail_type,
                                                                                  self.column, key))

    @property
    def alt_text_xpath(self):
        return self._make_alt_text('display')

    @property
    def alt_text(self):
        if self.app.supports_alt_text:
            return sx.AltText(
                text=sx.Text(xpath=self.alt_text_xpath)
            )

    def _xpath_template(self, type):
        return "if({key_as_condition}, {key_as_var_name}"

    def _xpath_template_context(self, type):
        return lambda item, i: {
            'key_as_condition': item.key_as_condition(self.xpath),
            'key_as_var_name': item.ref_to_key_variable(i, type)
        }


@register_format_type('late-flag')
class LateFlag(HideShortHeaderColumn):
    template_width = "11%"

    XPATH_FUNCTION = "if({xpath} = '', '*', if(today() - date({xpath}) > {column.late_flag}, '*', ''))"


@register_format_type('invisible')
class Invisible(HideShortColumn):

    @property
    def header(self):
        """
        header given for an invisible column to enable its display as a sort field in sort menu even
        when missing amongst display properties for case list headers
        refer: http://manage.dimagi.com/default.asp?232411
        """
        if self.sort_element and self.sort_element.has_display_values():
            header = sx.Header(
                text=sx.Text(locale_id=self.locale_id),
                width=self.template_width
            )
        else:
            header = super(Invisible, self).header
        return header

    @property
    def locale_id(self):
        return self.id_strings.detail_column_header_locale(
            self.module, self.detail_type, self.column
        )


@register_format_type('filter')
class Filter(HideShortColumn):

    @property
    def fields(self):
        return []


@register_format_type('markdown')
class Markdown(FormattedDetailColumn):

    @property
    def template_form(self):
        return 'markdown'


@register_format_type('address')
class Address(HideShortColumn):
    template_form = 'address'


@register_format_type('address-popup')
class AddressPopup(HideShortColumn):
    template_form = 'address-popup'


@register_format_type('picture')
class Picture(FormattedDetailColumn):
    template_form = 'image'


@register_format_type('clickable-icon')
class ClickableIcon(EnumImage):
    template_form = 'clickable-icon'


@register_format_type('audio')
class Audio(FormattedDetailColumn):
    template_form = 'audio'


@register_format_type('graph')
class Graph(FormattedDetailColumn):
    template_form = "graph"

    @property
    def template(self):
        def _locale_config(key):
            return self.id_strings.graph_configuration(
                self.module,
                self.detail_type,
                self.column,
                key
            )

        def _locale_series_config(index, key):
            return self.id_strings.graph_series_configuration(
                self.module,
                self.detail_type,
                self.column,
                index,
                key
            )

        def _locale_annotation(index):
            return self.id_strings.graph_annotation(
                self.module,
                self.detail_type,
                self.column,
                index
            )

        return sx.GraphTemplate.build(self.template_form, self.column.graph_configuration,
                                      locale_config=_locale_config, locale_series_config=_locale_series_config,
                                      locale_annotation=_locale_annotation)


@register_type_processor(const.FIELD_TYPE_ATTACHMENT)
class AttachmentXpathGenerator(BaseXpathGenerator):

    @property
    def xpath(self):
        return const.FIELD_TYPE_ATTACHMENT + "/" + self.column.field_property


@register_type_processor(const.FIELD_TYPE_PROPERTY)
class PropertyXpathGenerator(BaseXpathGenerator):

    @property
    def xpath(self):
        if self.column.model == 'product':
            return self.column.field

        parts = self.column.field.split('/')
        if self.column.model == 'case':
            parts[-1] = CASE_PROPERTY_MAP.get(parts[-1], parts[-1])
        property = parts.pop()
        indexes = parts

        use_absolute = indexes or property == '#owner_name'
        if use_absolute:
            case = CaseXPath('current()')
        else:
            case = CaseXPath('')

        if indexes and indexes[0] == 'user':
            case = CaseXPath(UsercaseXPath().case())
        elif indexes:
            instance_name = self.detail.get_instance_name(self.module)
            for index in indexes:
                case = case.index_id(index).case(instance_name=instance_name)

        if property == '#owner_name':
            return self.owner_name(case.property('@owner_id'))
        else:
            return case.property(property)

    @staticmethod
    def owner_name(owner_id):
        groups = XPath("instance('groups')/groups/group")
        group = groups.select('@id', owner_id)
        return XPath.if_(
            group.count().neq(0),
            group.slash('name'),
            XPath.if_(
                CommCareSession.userid.eq(owner_id),
                CommCareSession.username,
                XPath.string('')
            )
        )


@register_type_processor(const.FIELD_TYPE_INDICATOR)
class IndicatorXpathGenerator(BaseXpathGenerator):

    @property
    def xpath(self):
        indicator_set, indicator = self.column.field_property.split('/', 1)
        instance_id = self.id_strings.indicator_instance(indicator_set)
        return IndicatorXpath(instance_id).instance().slash(indicator)


@register_type_processor(const.FIELD_TYPE_LOCATION)
class LocationXpathGenerator(BaseXpathGenerator):

    @property
    def xpath(self):
        from corehq.apps.locations.util import parent_child
        hierarchy = parent_child(self.app.domain)
        return LocationXpath('commtrack:locations').location(self.column.field_property, hierarchy)


@register_type_processor(const.FIELD_TYPE_LEDGER)
class LedgerXpathGenerator(BaseXpathGenerator):

    @property
    def xpath(self):
        session_case_id = 'case_id_case_{0}'.format(self.module.case_type)
        section = self.column.field_property

        return "if({0} = 0 or {1} = 0 or {2} = 0, '', {3})".format(
            LedgerdbXpath(session_case_id).ledger().count(),
            LedgerdbXpath(session_case_id).ledger().section(section).count(),
            LedgerdbXpath(session_case_id).ledger().section(section).entry('current()/@id').count(),
            LedgerdbXpath(session_case_id).ledger().section(section).entry('current()/@id')
        )


@register_type_processor(const.FIELD_TYPE_SCHEDULE)
class ScheduleXpathGenerator(BaseXpathGenerator):

    @property
    def xpath(self):
        return "${}".format(self.column.field_property)
