from corehq.apps.app_manager import suite_xml as sx, xform

def get_column_generator(app, module, detail, column):
    return get_class_for_format(column.format)(app, module, detail, column)

def get_class_for_format(slug):
    return get_class_for_format._format_map.get(slug, FormattedDetailColumn)
get_class_for_format._format_map = {}

class register_format_type(object):

    def __init__(self, slug):
        self.slug = slug

    def __call__(self, klass):
        get_class_for_format._format_map[self.slug] = klass
        return klass


class FormattedDetailColumn(object):

    header_width = None
    template_width = None
    template_form = None

    def __init__(self, app, module, detail, column):
        from corehq.apps.app_manager.suite_xml import IdStrings
        self.app = app
        self.module = module
        self.detail = detail
        self.column = column
        self.id_strings = IdStrings()

    @property
    def locale_id(self):
        return self.id_strings.detail_column_header_locale(self.module, self.detail, self.column)

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
    def xpath(self):
        return self.column.xpath

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
        if self.sort_xpath_function and self.detail.display == 'short':
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
        for key in self.column.enum:
            parts.append(
                u"if({xpath} = '{key}', $k{key}, ".format(key=key, xpath=self.xpath)
            )
        parts.append("''")
        parts.append(")" * len(self.column.enum))
        return ''.join(parts)

    @property
    def variables(self):
        variables = {}
        for key in self.column.enum:
            v_key = u"k{key}".format(key=key)
            v_val= self.id_strings.detail_column_enum_variable(self.module, self.detail, self.column, key)
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


# todo: These two were never actually supported, and 'advanced' certainly never worked
# but for some reason have been hanging around in the suite.xml template since September 2010
#
#@register_format_type('advanced')
#class Advanced(HideShortColumn):
#    pass
#
#@register_format_type('enum-image')
#class EnumImage(HideShortColumn):
#    template_form = 'image'
