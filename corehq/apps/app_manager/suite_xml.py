from collections import namedtuple
from django.core.urlresolvers import reverse
from lxml import etree
from eulxml.xmlmap import StringField, XmlObject, IntegerField, NodeListField, NodeField
from .exceptions import MediaResourceError, ParentModuleReferenceError, SuiteValidationError
from corehq.apps.app_manager.util import split_path, create_temp_sort_column
from corehq.apps.app_manager.xform import SESSION_CASE_ID
from dimagi.utils.decorators.memoized import memoized
from dimagi.utils.web import get_url_base

FIELD_TYPE_INDICATOR = 'indicator'
FIELD_TYPE_PROPERTY = 'property'


class OrderedXmlObject(XmlObject):
    ORDER = ()

    def __init__(self, *args, **kwargs):
        ordered_pairs = []
        for attr in self.ORDER:
            value = kwargs.pop(attr, None)
            if value:
                ordered_pairs.append((attr, value))
        super(OrderedXmlObject, self).__init__(*args, **kwargs)
        for attr, value in ordered_pairs:
            setattr(self, attr, value)


class IdNode(XmlObject):
    id = StringField('@id')


class XpathVariable(XmlObject):
    ROOT_NAME = 'variable'
    name = StringField('@name')

    locale_id = StringField('locale/@id')


class Xpath(XmlObject):
    ROOT_NAME = 'xpath'
    function = StringField('@function')
    variables = NodeListField('variable', XpathVariable)


class Text(XmlObject):
    """
    <text>                     <!----------- Exactly one. Will be present wherever text can be defined. Contains a sequential list of string elements to be concatenated to form the text body.-->
        <xpath function="">   <!------------ 0 or More. An xpath function whose result is a string. References a data model if used in a context where one exists. -->
            <variable name=""/> <!------------ 0 or More. Variable for the localized string. Variable elements can support any child elements that <body> can. -->
        </xpath>
        <locale id="">         <!------------ 0 or More. A localized string. id can be referenced here or as a child-->
            <id/>              <!------------ At Most One. The id of the localized string (if not provided as an attribute -->
            <argument key=""/> <!------------ 0 or More. Arguments for the localized string. Key is optional. Arguments can support any child elements that <body> can. -->
        </locale>
    </text>
    """

    ROOT_NAME = 'text'

    xpath = NodeField('xpath', Xpath)
    xpath_function = StringField('xpath/@function')

    locale_id = StringField('locale/@id')


class AbstractResource(OrderedXmlObject):
    ORDER = ('id', 'version', 'local', 'remote')
    LOCATION_TEMPLATE = 'resource/location[@authority="%s"]'

    local = StringField(LOCATION_TEMPLATE % 'local', required=True)
    remote = StringField(LOCATION_TEMPLATE % 'remote', required=True)

    version = IntegerField('resource/@version')
    id = StringField('resource/@id')


class XFormResource(AbstractResource):
    ROOT_NAME = 'xform'


class LocaleResource(AbstractResource):
    ROOT_NAME = 'locale'
    language = StringField('@language')


class MediaResource(AbstractResource):
    ROOT_NAME = 'media'
    path = StringField('@path')


class Display(OrderedXmlObject):
    ROOT_NAME = 'display'
    ORDER = ('text', 'media_image', 'media_audio')
    text = NodeField('text', Text)
    media_image = StringField('media/@image')
    media_audio = StringField('media/@audio')


class DisplayNode(XmlObject):
    """Any node that has the awkward text-or-display subnode, like Command or Menu"""
    text = NodeField('text', Text)
    display = NodeField('display', Display)

    def __init__(self, locale_id=None, media_image=None, media_audio=None, **kwargs):
        super(DisplayNode, self).__init__(**kwargs)
        if locale_id is None:
            text = None
        else:
            text = Text(locale_id=locale_id)
            
        if media_image or media_audio:
            self.display = Display(text=text, media_image=media_image, media_audio=media_audio)
        else:
            self.text = text


class Command(DisplayNode, IdNode):
    ROOT_NAME = 'command'
    relevant = StringField('@relevant')


class Instance(IdNode, OrderedXmlObject):
    ROOT_NAME = 'instance'
    ORDER = ('id', 'src')

    src = StringField('@src')


class SessionDatum(IdNode, OrderedXmlObject):
    ROOT_NAME = 'datum'
    ORDER = ('id', 'nodeset', 'value', 'detail_select', 'detail_confirm')

    nodeset = StringField('@nodeset')
    value = StringField('@value')
    detail_select = StringField('@detail-select')
    detail_confirm = StringField('@detail-confirm')


class Entry(XmlObject):
    ROOT_NAME = 'entry'

    form = StringField('form')
    command = NodeField('command', Command)
    instance = NodeField('instance', Instance)
    instances = NodeListField('instance', Instance)

    datums = NodeListField('session/datum', SessionDatum)
    datum = NodeField('session/datum', SessionDatum)


class Menu(DisplayNode, IdNode):
    ROOT_NAME = 'menu'

    commands = NodeListField('command', Command)


class AbstractTemplate(XmlObject):
    form = StringField('@form', choices=['image', 'phone', 'address'])
    width = IntegerField('@width')
    text = NodeField('text', Text)


class Template(AbstractTemplate):
    ROOT_NAME = 'template'


class Header(AbstractTemplate):
    ROOT_NAME = 'header'


class Sort(AbstractTemplate):
    ROOT_NAME = 'sort'

    type = StringField('@type')
    order = StringField('@order')
    direction = StringField('@direction')


class Field(OrderedXmlObject):
    ROOT_NAME = 'field'
    ORDER = ('header', 'template', 'sort_node')

    sort = StringField('@sort')
    header = NodeField('header', Header)
    template = NodeField('template', Template)
    sort_node = NodeField('sort', Sort)


class DetailVariable(XmlObject):
    ROOT_NAME = '_'
    function = StringField('@function')

    def get_name(self):
        return self.node.tag

    def set_name(self, value):
        self.node.tag = value

    name = property(get_name, set_name)


class DetailVariableList(XmlObject):
    ROOT_NAME = 'variables'

    variables = NodeListField('_', DetailVariable)


class Detail(IdNode):
    """
    <detail id="">
        <title><text/></title>
        <variables>
            <__ function=""/>
        </variables>
        <field sort="">
            <header form="" width=""><text/></header>
            <template form=""  width=""><text/></template>
        </field>
    </detail>
    """

    ROOT_NAME = 'detail'

    title = NodeField('title/text', Text)
    fields = NodeListField('field', Field)
    _variables = NodeField('variables', DetailVariableList)

    def _init_variables(self):
        if self._variables is None:
            self._variables = DetailVariableList()

    def get_variables(self):
        self._init_variables()
        return self._variables.variables

    def set_variables(self, value):
        self._init_variables()
        self._variables.variables = value

    variables = property(get_variables, set_variables)


class Fixture(IdNode):
    ROOT_NAME = 'fixture'

    user_id = StringField('@user_id')

    def set_content(self, xml):
        for child in self.node:
            self.node.remove(child)
        self.node.append(xml)


class Suite(XmlObject):
    ROOT_NAME = 'suite'

    version = IntegerField('@version')

    xform_resources = NodeListField('xform', XFormResource)
    locale_resources = NodeListField('locale', LocaleResource)
    media_resources = NodeListField('locale', MediaResource)

    details = NodeListField('detail', Detail)
    entries = NodeListField('entry', Entry)
    menus = NodeListField('menu', Menu)

    fixtures = NodeListField('fixture', Fixture)


class IdStrings(object):

    def homescreen_title(self):
        return 'homescreen.title'

    def app_display_name(self):
        return "app.display.name"

    def xform_resource(self, form):
        return form.unique_id

    def locale_resource(self, lang):
        return u'app_{lang}_strings'.format(lang=lang)

    def media_resource(self, multimedia_id, name):
        return u'media-{id}-{name}'.format(id=multimedia_id, name=name)

    def detail(self, module, detail):
        return u"m{module.id}_{detail.type}".format(module=module, detail=detail)

    def detail_title_locale(self, module, detail):
        return u"m{module.id}.{detail.type}.title".format(module=module, detail=detail)

    def detail_column_header_locale(self, module, detail, column):
        return u"m{module.id}.{detail.type}.{d.model}_{d.field}_{d_id}.header".format(
            detail=detail,
            module=module,
            d=column,
            d_id=column.id + 1
        )

    def detail_column_enum_variable(self, module, detail, column, key):
        return u"m{module.id}.{detail.type}.{d.model}_{d.field}_{d_id}.enum.k{key}".format(
            module=module,
            detail=detail,
            d=column,
            d_id=column.id + 1,
            key=key,
        )

    def menu(self, module):
        return u"m{module.id}".format(module=module)

    def module_locale(self, module):
        return module.get_locale_id()

    def form_locale(self, form):
        return form.get_locale_id()

    def form_command(self, form):
        return form.get_command_id()

    def case_list_command(self, module):
        return module.get_case_list_command_id()

    def case_list_locale(self, module):
        return module.get_case_list_locale_id()

    def referral_list_command(self, module):
        """1.0 holdover"""
        return module.get_referral_list_command_id()

    def referral_list_locale(self, module):
        """1.0 holdover"""
        return module.get_referral_list_locale_id()

    def indicator_instance(self, indicator_set_name):
        return u"indicators_%s" % indicator_set_name


def get_detail_column_infos(detail):
    """
    This is not intented to be a widely used format
    just a packaging of column info into a form most convenient for rendering
    """
    from corehq.apps.app_manager.models import SortElement

    if detail.type != 'case_short':
        return [(column, (None, None)) for column in detail.get_columns()]

    DetailColumnInfo = namedtuple('DetailColumnInfo',
                                  'column sort_element order')

    if detail.sort_elements:
        sort_elements = detail.sort_elements
    elif detail.columns:
        sort_elements = [SortElement(
            field=detail.get_column(0).field,
            type='string',
            direction='ascending',
        )]
    else:
        sort_elements = []

    # order is 1-indexed
    sort_elements = dict((s.field, (s, i + 1))
                         for i, s in enumerate(sort_elements))
    columns = []
    for column in detail.get_columns():
        sort_element, order = sort_elements.pop(column.field, (None, None))
        columns.append(DetailColumnInfo(column, sort_element, order))

    # sort elements is now populated with only what's not in any column
    # add invisible columns for these
    for field, (sort_element, order) in sort_elements.items():
        column = create_temp_sort_column(field, len(columns))
        columns.append(DetailColumnInfo(column, sort_element, order))
    return columns


class SuiteGenerator(object):
    def __init__(self, app):
        self.app = app
        # this is actually so slow it's worth caching
        self.modules = list(self.app.get_modules())
        self.id_strings = IdStrings()

    @property
    def xform_resources(self):
        first = []
        last = []
        for form_stuff in self.app.get_forms(bare=False):
            if form_stuff['type'] == 'module_form':
                path = './modules-{module.id}/forms-{form.id}.xml'.format(**form_stuff)
                this_list = first
            else:
                path = './user_registration.xml'
                this_list = last
            this_list.append(XFormResource(
                id=self.id_strings.xform_resource(form_stuff['form']),
                version=form_stuff['form'].get_version(),
                local=path,
                remote=path,
            ))
        for x in first:
            yield x
        for x in last:
            yield x

    @property
    def locale_resources(self):
        for lang in ["default"] + self.app.build_langs:
            path = './{lang}/app_strings.txt'.format(lang=lang)
            yield LocaleResource(
                language=lang,
                id=self.id_strings.locale_resource(lang),
                version=self.app.version,
                local=path,
                remote=path,
            )

    @property
    def media_resources(self):
        PREFIX = 'jr://file/'
        # you have to call remove_unused_mappings
        # before iterating through multimedia_map
        self.app.remove_unused_mappings()
        for path, m in self.app.multimedia_map.items():
            if path.startswith(PREFIX):
                path = path[len(PREFIX):]
            else:
                raise MediaResourceError('%s does not start with jr://file/commcare/' % path)
            path, name = split_path(path)
            # CommCare assumes jr://media/,
            # which is an alias to jr://file/commcare/media/
            # so we need to replace 'jr://file/' with '../../'
            # (this is a hack)
            path = '../../' + path
            multimedia_id = m.multimedia_id
            yield MediaResource(
                id=self.id_strings.media_resource(multimedia_id, name),
                path=path,
                version=m.version,
                local=None,
                remote=get_url_base() + reverse(
                    'hqmedia_download',
                    args=[m.media_type, multimedia_id]
                ) + name
            )

    @property
    @memoized
    def details(self):

        r = []
        from corehq.apps.app_manager.detail_screen import get_column_generator
        if not self.app.use_custom_suite:
            for module in self.modules:
                for detail in module.get_details():
                    detail_column_infos = get_detail_column_infos(detail)

                    if detail_column_infos and detail.type in ('case_short', 'case_long'):
                        d = Detail(
                            id=self.id_strings.detail(module, detail),
                            title=Text(locale_id=self.id_strings.detail_title_locale(module, detail))
                        )

                        for column_info in detail_column_infos:
                            fields = get_column_generator(self.app, module, detail, *column_info).fields
                            d.fields.extend(fields)

                        try:
                            if not self.app.enable_multi_sort:
                                d.fields[0].sort = 'default'
                        except IndexError:
                            pass
                        else:
                            # only yield the Detail if it has Fields
                            r.append(d)

        return r

    def get_filter_xpath(self, module, delegation=False):
        from corehq.apps.app_manager.detail_screen import Filter
        short_detail = module.details[0]
        filters = []
        for column in short_detail.get_columns():
            if column.format == 'filter':
                filters.append("(%s)" % Filter(self.app, module, short_detail, column).filter_xpath)
        if filters:
            xpath = '[%s]' % (' and '.join(filters))
        else:
            xpath = ''

        if delegation:
            xpath += "[index/parent/@case_type = '%s']" % module.case_type
            xpath += "[start_date = '' or double(date(start_date)) <= double(now())]"
        return xpath

    def get_nodeset_xpath(self, module, use_filter):
        return "instance('casedb')/casedb/case[@case_type='{case_type}'][@status='open']{filter_xpath}".format(
            case_type=module.case_type,
            filter_xpath=self.get_filter_xpath(module) if use_filter else '',
        )

    def get_parent_filter(self, module, parent_id):
        return "[index/{relationship}=instance('commcaresession')/session/data/{parent_id}]".format(
            relationship=module.parent_select.relationship,
            parent_id=parent_id,
        )

    def get_module_by_id(self, module_id):
        try:
            [parent_module] = (
                module for module in self.app.get_modules()
                if module.unique_id == module_id
            )
        except ValueError:
            raise ParentModuleReferenceError(
                "Module %s in app %s not found" % (module_id, self.app)
            )
        else:
            return parent_module

    def get_select_chain(self, module):
        select_chain = [module]
        current_module = module
        while current_module.parent_select.active:
            current_module = self.get_module_by_id(
                current_module.parent_select.module_id
            )
            select_chain.append(current_module)
        return select_chain

    @property
    def entries(self):
        def add_case_stuff(module, e, use_filter=False):
            def get_instances():
                yield Instance(id='casedb', src='jr://instance/casedb')
                if (any(form.form_filter for form in module.get_forms())
                    and module.all_forms_require_a_case()) \
                    or module.parent_select.active:
                    yield Instance(id='commcaresession',
                                   src='jr://instance/session')

                indicator_sets = []
                for detail in module.get_details():
                    for column in detail.get_columns():
                        if column.field_type == FIELD_TYPE_INDICATOR:
                            indicator_set, _ = column.field_property.split('/', 1)
                            if indicator_set not in indicator_sets:
                                indicator_sets.append(indicator_set)
                                yield Instance(id=self.id_strings.indicator_instance(indicator_set),
                                       src='jr://fixture/indicators:%s' % indicator_set)

            e.instances.extend(get_instances())

            detail_ids = [detail.id for detail in self.details]

            def get_detail_id_safe(module, detail_type):
                detail_id = self.id_strings.detail(
                    module=module,
                    detail=module.get_detail(detail_type)
                )
                return detail_id if detail_id in detail_ids else None

            select_chain = self.get_select_chain(module)
            # generate names ['child_id', 'parent_id', 'parent_parent_id', ...]
            datum_ids = [('parent_' * i or 'case_') + 'id'
                         for i in range(len(select_chain))]
            # iterate backwards like
            # [..., (2, 'parent_parent_id'), (1, 'parent_id'), (0, 'child_id')]
            for i, module in reversed(list(enumerate(select_chain))):
                try:
                    parent_id = datum_ids[i + 1]
                except IndexError:
                    parent_filter = ''
                else:
                    parent_filter = self.get_parent_filter(module, parent_id)
                e.datums.append(SessionDatum(
                    id=datum_ids[i],
                    nodeset=(self.get_nodeset_xpath(module, use_filter)
                             + parent_filter),
                    value="./@case_id",
                    detail_select=get_detail_id_safe(module, 'case_short'),
                    detail_confirm=(
                        get_detail_id_safe(module, 'case_long')
                        if i == 0 else None
                    )
                ))

        for module in self.modules:
            for form in module.get_forms():
                e = Entry()
                e.form = form.xmlns
                e.command=Command(
                    id=self.id_strings.form_command(form),
                    locale_id=self.id_strings.form_locale(form),
                    media_image=form.media_image,
                    media_audio=form.media_audio,
                )
                if form.requires == "case":
                    add_case_stuff(module, e, use_filter=True)
                yield e
            if module.case_list.show:
                e = Entry(
                    command=Command(
                        id=self.id_strings.case_list_command(module),
                        locale_id=self.id_strings.case_list_locale(module),
                    )
                )
                add_case_stuff(module, e, use_filter=False)
                yield e
    @property
    def menus(self):
        for module in self.modules:
            menu = Menu(
                id='root' if module.put_in_root else self.id_strings.menu(module),
                locale_id=self.id_strings.module_locale(module),
                media_image=module.media_image,
                media_audio=module.media_audio,
            )

            def get_commands():
                for form in module.get_forms():
                    command = Command(id=self.id_strings.form_command(form))
                    if module.all_forms_require_a_case() and \
                            not module.put_in_root and \
                            getattr(form, 'form_filter', None):
                        command.relevant = form.form_filter.replace('.',
                            SESSION_CASE_ID.case()
                        )
                    yield command

                if module.case_list.show:
                    yield Command(id=self.id_strings.case_list_command(module))

            menu.commands.extend(get_commands())

            yield menu

    @property
    def fixtures(self):
        if self.app.case_sharing:
            f = Fixture(id='user-groups')
            f.user_id = 'demo_user'
            groups = etree.fromstring("""
                <groups>
                    <group id="demo_user_group_id">
                        <name>Demo Group</name>
                    </group>
                </groups>
            """)
            f.set_content(groups)
            yield f

    def generate_suite(self, sections=None):
        sections = sections or (
            'xform_resources',
            'locale_resources',
            'details',
            'entries',
            'menus',
            'fixtures',
        )
        suite = Suite()
        suite.version = self.app.version

        def add_to_suite(attr):
            getattr(suite, attr).extend(getattr(self, attr))

        map(add_to_suite, sections)
        return suite.serializeDocument(pretty=True)


def validate_suite(suite):
    if isinstance(suite, unicode):
        suite = suite.encode('utf8')
    if isinstance(suite, str):
        suite = etree.fromstring(suite)
    if isinstance(suite, etree._Element):
        suite = Suite(suite)
    assert isinstance(suite, Suite),\
        'Could not convert suite to a Suite XmlObject: %r' % suite

    def is_unique_list(things):
        return len(set(things)) == len(things)

    for detail in suite.details:
        orders = [field.sort_node.order for field in detail.fields
                  if field and field.sort_node]
        if not is_unique_list(orders):
            raise SuiteValidationError('field/sort/@order must be unique per detail')
