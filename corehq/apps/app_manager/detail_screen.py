from corehq.apps.app_manager import id_strings
from corehq.apps.app_manager.suite_xml import xml_models as sx
from corehq.apps.app_manager.suite_xml import const
from corehq.apps.app_manager.util import is_sort_only_column
from corehq.apps.app_manager.xpath import (
    CaseXPath,
    CommCareSession,
    IndicatorXpath,
    LedgerdbXpath,
    LocationXpath,
    XPath,
    dot_interpolate,
    UserCaseXPath)
from corehq.apps.hqmedia.models import CommCareMultimedia
import re

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
                         order=None, detail_type=None):
    cls = get_class_for_format(column.format)
    return cls(app, module, detail, column, sort_element, order, detail_type=detail_type)


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
    cls = get_class_for_type(column.field_type)
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
                 order=None, detail_type=None):
        self.app = app
        self.module = module
        self.detail = detail
        self.detail_type = detail_type
        self.column = column
        self.sort_element = sort_element
        self.order = order
        self.id_strings = id_strings

    @property
    def locale_id(self):
        if not is_sort_only_column(self.column):
            return self.id_strings.detail_column_header_locale(
                self.module, self.detail_type, self.column,
            )
        else:
            return None

    @property
    def header(self):
        header = sx.Header(
            text=sx.Text(locale_id=self.locale_id),
            width=self.header_width
        )
        return header

    variables = None

    @property
    def template(self):
        template = sx.Template(
            text=sx.Text(xpath_function=self.xpath_function),
            form=self.template_form,
            width=self.template_width,
        )
        if self.variables:
            for key, value in sorted(self.variables.items()):
                template.text.xpath.variables.node.append(
                    sx.XpathVariable(name=key, locale_id=value).node
                )

        return template

    @property
    def sort_node(self):
        if not (self.app.enable_multi_sort and self.detail.display == 'short'):
            return

        sort = None

        if self.sort_xpath_function:
            sort = sx.Sort(
                text=sx.Text(xpath_function=self.sort_xpath_function),
                type=self.SORT_TYPE,
            )

        if self.sort_element:
            if not sort:
                sort_type = {
                    'date': 'string',
                    'plain': 'string',
                    'distance': 'double'
                }.get(self.sort_element.type, self.sort_element.type)

                sort = sx.Sort(
                    text=sx.Text(xpath_function=self.xpath_function),
                    type=sort_type,
                )

            if self.sort_element.type == 'distance':
                sort.text.xpath_function = self.evaluate_template(Distance.SORT_XPATH_FUNCTION)

            sort.order = self.order
            sort.direction = self.sort_element.direction

            # Flag field as index by making order "-2"
            # this is for the CACHE_AND_INDEX toggle
            # (I know, I know, it's hacky - blame Clayton)
            if sort.type == 'index':
                sort.type = 'string'
                sort.order = -2

        return sort

    @property
    def xpath(self):
        return get_column_xpath_generator(self.app, self.module, self.detail,
                                          self.column).xpath

    XPATH_FUNCTION = u"{xpath}"

    def evaluate_template(self, template):
        if template:
            return template.format(
                xpath=self.xpath,
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
    def fields(self):
        if self.app.enable_multi_sort:
            yield sx.Field(
                header=self.header,
                template=self.template,
                sort_node=self.sort_node,
            )
        elif self.sort_xpath_function and self.detail.display == 'short':
            yield sx.Field(
                header=self.header,
                template=self.hidden_template,
            )
            yield sx.Field(
                header=self.hidden_header,
                template=self.template,
            )
        else:
            yield sx.Field(
                header=self.header,
                template=self.template,
            )


class HideShortHeaderColumn(FormattedDetailColumn):

    @property
    def header(self):
        if self.detail.display == 'short':
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
        if self.detail.display == 'short':
            return 0


@register_format_type('plain')
class Plain(FormattedDetailColumn):
    pass


@register_format_type('date')
class Date(FormattedDetailColumn):

    XPATH_FUNCTION = u"if({xpath} = '', '', format_date(date(if({xpath} = '', 0, {xpath})),'short'))"

    SORT_XPATH_FUNCTION = u"{xpath}"


@register_format_type('time-ago')
class TimeAgo(FormattedDetailColumn):
    XPATH_FUNCTION = u"if({xpath} = '', '', string(int((today() - date({xpath})) div {column.time_ago_interval})))"
    SORT_XPATH_FUNCTION = u"{xpath}"


@register_format_type('distance')
class Distance(FormattedDetailColumn):
    XPATH_FUNCTION = u"if(here() = '', '', if({xpath} = '', '', concat(round(distance({xpath}, here()) div 1000), ' km')))"
    SORT_XPATH_FUNCTION = u'round(distance({xpath}, here()))'
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
        if type == 'sort':
            xpath_fragment_template = u"if({xpath} = '{key}', {i}, "
        elif type == 'display':
            xpath_fragment_template = u"if({xpath} = '{key}', ${key_as_var}, "
        else:
            raise ValueError('type must be in sort, display')

        parts = []
        for i, item in enumerate(self.column.enum):
            parts.append(
                xpath_fragment_template.format(
                    key=item.key,
                    key_as_var=item.key_as_variable,
                    xpath=self.xpath,
                    i=i,
                )
            )
        parts.append(u"''")
        parts.append(u")" * len(self.column.enum))
        return ''.join(parts)

    @property
    def xpath_function(self):
        return self._make_xpath(type='display')

    @property
    def sort_xpath_function(self):
        return self._make_xpath(type='sort')

    @property
    def variables(self):
        variables = {}
        for item in self.column.enum:
            v_key = item.key_as_variable
            v_val = self.id_strings.detail_column_enum_variable(
                self.module, self.detail_type, self.column, v_key)
            variables[v_key] = v_val
        return variables


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

    def _make_xpath(self, type):
        parts = []
        for i, item in enumerate(self.column.enum):

            xpath_fragment_template = u"if({key_as_condition}, {key_as_var_name}".format(
                key_as_condition=item.key_as_condition(self.xpath),
                key_as_var_name=item.ref_to_key_variable(i, type)
            )

            parts.append(xpath_fragment_template)

        parts.append(u"''")
        parts.append(u")" * (len(self.column.enum)))
        return ''.join(parts)


@register_format_type('late-flag')
class LateFlag(HideShortHeaderColumn):
    template_width = "11%"

    XPATH_FUNCTION = u"if({xpath} = '', '*', if(today() - date({xpath}) > {column.late_flag}, '*', ''))"


@register_format_type('invisible')
class Invisible(HideShortColumn):
    pass


@register_format_type('filter')
class Filter(HideShortColumn):

    @property
    def fields(self):
        return []


@register_format_type('calculate')
class Calculate(FormattedDetailColumn):

    @property
    def variables(self):
        variables = {}
        if re.search(r'\$lang', self.column.calc_xpath):
            variables['lang'] = self.id_strings.current_language()
        return variables

    @property
    def xpath_function(self):
        return dot_interpolate(self.column.calc_xpath, self.xpath)


@register_format_type('address')
class Address(HideShortColumn):
    template_form = 'address'
    template_width = 0


@register_format_type('picture')
class Picture(FormattedDetailColumn):
    template_form = 'image'


@register_format_type('audio')
class Audio(FormattedDetailColumn):
    template_form = 'audio'


@register_format_type('graph')
class Graph(FormattedDetailColumn):
    template_form = "graph"

    @property
    def template(self):
        template = sx.GraphTemplate(
            form=self.template_form,
            graph=sx.Graph(
                type=self.column.graph_configuration.graph_type,
                series=[
                    sx.Series(
                        nodeset=s.data_path,
                        x_function=s.x_function,
                        y_function=s.y_function,
                        radius_function=s.radius_function,
                        configuration=sx.ConfigurationGroup(
                            configs=(
                                [
                                    # TODO: It might be worth wrapping
                                    #       these values in quotes (as appropriate)
                                    #       to prevent the user from having to
                                    #       figure out why their unquoted colors
                                    #       aren't working.
                                    sx.ConfigurationItem(id=k, xpath_function=v)
                                    for k, v in s.config.iteritems()
                                ] + [
                                    sx.ConfigurationItem(
                                        id=k,
                                        locale_id=self.id_strings.graph_series_configuration(
                                            self.module,
                                            self.detail_type,
                                            self.column,
                                            index,
                                            k
                                        )
                                    )
                                    for k, v in s.locale_specific_config.iteritems()
                                ]
                            )
                        )
                    )
                    for index, s in enumerate(self.column.graph_configuration.series)],
                configuration=sx.ConfigurationGroup(
                    configs=(
                        [
                            sx.ConfigurationItem(id=k, xpath_function=v)
                            for k, v
                            in self.column.graph_configuration.config.iteritems()
                        ] + [
                            sx.ConfigurationItem(
                                id=k,
                                locale_id=self.id_strings.graph_configuration(
                                    self.module,
                                    self.detail_type,
                                    self.column,
                                    k
                                )
                            )
                            for k, v
                            in self.column.graph_configuration.locale_specific_config.iteritems()
                        ]
                    )
                ),
                annotations=[
                    sx.Annotation(
                        x=sx.Text(xpath_function=a.x),
                        y=sx.Text(xpath_function=a.y),
                        text=sx.Text(
                            locale_id=self.id_strings.graph_annotation(
                                self.module,
                                self.detail_type,
                                self.column,
                                i
                            )
                        )
                    )
                    for i, a in enumerate(
                        self.column.graph_configuration.annotations
                    )]
            )
        )

        # TODO: what are self.variables and do I need to care about them here?
        # (see FormattedDetailColumn.template)

        return template


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

        use_relative = property != '#owner_name'
        if use_relative:
            case = CaseXPath('')
        else:
            case = CaseXPath(u'current()')

        if indexes and indexes[0] == 'user':
            case = CaseXPath(UserCaseXPath().case())
        else:
            for index in indexes:
                case = case.index_id(index).case()

        if property == '#owner_name':
            return self.owner_name(case.property('@owner_id'))
        else:
            return case.property(property)

    @staticmethod
    def owner_name(owner_id):
        groups = XPath(u"instance('groups')/groups/group")
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
            LedgerdbXpath(session_case_id).ledger().section(section).entry(u'current()/@id').count(),
            LedgerdbXpath(session_case_id).ledger().section(section).entry(u'current()/@id')
        )


@register_type_processor(const.FIELD_TYPE_SCHEDULE)
class ScheduleXpathGenerator(BaseXpathGenerator):

    @property
    def xpath(self):
        return "${}".format(self.column.field_property)
