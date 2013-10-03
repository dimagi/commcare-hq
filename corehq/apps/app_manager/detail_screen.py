from corehq.apps.app_manager import suite_xml as sx
from corehq.apps.app_manager.xform import CaseXPath, IndicatorXpath

CASE_PROPERTY_MAP = {
    # IMPORTANT: if you edit this you probably want to also edit
    # the corresponding map in cloudcare
    # (corehq.apps.cloudcare.static.cloudcare.js.backbone.cases.js)
    'external-id': 'external_id',
    'date-opened': 'date_opened',
    'status': '@status',
    'name': 'case_name',
}


def get_column_generator(app, module, detail, column, sort_element=None,
                         order=None):
    cls = get_class_for_format(column.format)
    return cls(app, module, detail, column, sort_element, order)


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
        self.id_strings = sx.IdStrings()

    @property
    def xpath(self):
        return self.column.field


class FormattedDetailColumn(object):

    header_width = None
    template_width = None
    template_form = None

    def __init__(self, app, module, detail, column, sort_element=None,
                 order=None):
        self.app = app
        self.module = module
        self.detail = detail
        self.column = column
        self.sort_element = sort_element
        self.order = order
        self.id_strings = sx.IdStrings()

    @property
    def locale_id(self):
        return self.id_strings.detail_column_header_locale(self.module,
                                                           self.detail,
                                                           self.column)

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
                type='string',
            )

        if self.sort_element:
            if not sort:
                # these have to be distinguished for the UI to be able to give
                # user friendly choices
                if self.sort_element.type in ('date', 'plain'):
                    sort_type = 'string'
                else:
                    sort_type = self.sort_element.type
                sort = sx.Sort(
                    text=sx.Text(xpath_function=self.xpath_function),
                    type=sort_type,
                )

            sort.order = self.order
            sort.direction = self.sort_element.direction

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
    def header_width(self):
        if self.detail.display == 'short':
            return 0


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


@register_format_type('phone')
class Phone(FormattedDetailColumn):
    @property
    def template_form(self):
        if self.detail.display == 'long':
            return 'phone'


@register_format_type('enum')
class Enum(FormattedDetailColumn):

    @property
    def xpath_function(self):
        parts = []
        for key in sorted(self.column.enum.keys()):
            parts.append(
                u"if({xpath} = '{key}', $k{key}, ".format(key=key,
                                                          xpath=self.xpath)
            )
        parts.append("''")
        parts.append(")" * len(self.column.enum))
        return ''.join(parts)

    @property
    def variables(self):
        variables = {}
        for key in self.column.enum:
            v_key = u"k{key}".format(key=key)
            v_val= self.id_strings.detail_column_enum_variable(self.module,
                                                               self.detail,
                                                               self.column,
                                                               key)
            variables[v_key] = v_val
        return variables

@register_format_type('late-flag')
class LateFlag(HideShortHeaderColumn):

    template_width = "10%"

    XPATH_FUNCTION = u"if({xpath} = '', '*', if(today() - date({xpath}) > {column.late_flag}, '*', ''))"


@register_format_type('invisible')
class Invisible(HideShortColumn):
    pass


@register_format_type('filter')
class Filter(HideShortColumn):

    @property
    def fields(self):
        return []

    @property
    def filter_xpath(self):
        return self.column.filter_xpath.replace('.', self.xpath)


@register_format_type('address')
class Address(HideShortColumn):
    template_form = 'address'
    template_width = 0


@register_type_processor(sx.FIELD_TYPE_PROPERTY)
class PropertyXpathGenerator(BaseXpathGenerator):
    @property
    def xpath(self):
        parts = self.column.field.split('/')
        parts[-1] = CASE_PROPERTY_MAP.get(parts[-1], parts[-1])
        property = parts.pop()
        indexes = parts

        case = CaseXPath('')
        for index in indexes:
            case = case.index_id(index).case()
        return case.property(property)


@register_type_processor(sx.FIELD_TYPE_INDICATOR)
class IndicatorXpathGenerator(BaseXpathGenerator):
    @property
    def xpath(self):
        indicator_set, indicator = self.column.field_property.split('/', 1)
        instance_id = self.id_strings.indicator_instance(indicator_set)
        return IndicatorXpath(instance_id).indicator(indicator)
