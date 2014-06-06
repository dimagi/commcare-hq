from collections import namedtuple
from corehq.apps.app_manager import id_strings
import urllib
from django.core.urlresolvers import reverse
from lxml import etree
from eulxml.xmlmap import StringField, XmlObject, IntegerField, NodeListField, NodeField
from corehq.apps.app_manager.templatetags.xforms_extras import trans
from corehq.apps.app_manager.const import CAREPLAN_GOAL, CAREPLAN_TASK
from corehq.apps.hqmedia.models import HQMediaMapItem
from .exceptions import MediaResourceError, ParentModuleReferenceError, SuiteValidationError
from corehq.apps.app_manager.util import split_path, create_temp_sort_column, languages_mapping
from corehq.apps.app_manager.xform import SESSION_CASE_ID, autoset_owner_id_for_open_case, autoset_owner_id_for_subcase
from dimagi.utils.decorators.memoized import memoized
from dimagi.utils.web import get_url_base
from .xpath import dot_interpolate, CaseIDXPath, session_var, CaseTypeXpath, FixtureXpath

FIELD_TYPE_INDICATOR = 'indicator'
FIELD_TYPE_LOCATION = 'location'
FIELD_TYPE_PROPERTY = 'property'
FIELD_TYPE_LEDGER = 'ledger'


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


class LocaleArgument(XmlObject):
    ROOT_NAME = 'argument'
    key = StringField('@key')
    value = StringField('.')


class Locale(XmlObject):
    ROOT_NAME = 'locale'
    id = StringField('@id')
    arguments = NodeListField('argument', LocaleArgument)


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

    locale = NodeField('locale', Locale)
    locale_id = StringField('locale/@id')


class AbstractResource(OrderedXmlObject):
    ORDER = ('id', 'version', 'local', 'remote')
    LOCATION_TEMPLATE = 'resource/location[@authority="%s"]'

    local = StringField(LOCATION_TEMPLATE % 'local', required=True)
    remote = StringField(LOCATION_TEMPLATE % 'remote', required=True)

    version = IntegerField('resource/@version')
    id = StringField('resource/@id')
    descriptor = StringField('resource/@descriptor')


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
    ORDER = ('id', 'nodeset', 'value', 'function', 'detail_select', 'detail_confirm')

    nodeset = StringField('@nodeset')
    value = StringField('@value')
    function = StringField('@function')
    detail_select = StringField('@detail-select')
    detail_confirm = StringField('@detail-confirm')


class StackDatum(IdNode):
    ROOT_NAME = 'datum'

    value = StringField('@value')


class BaseFrame(XmlObject):
    if_clause = StringField('@if')


class CreatePushBase(IdNode, BaseFrame):
    def add_command(self, command):
        node = etree.SubElement(self.node, 'command')
        node.text = command

    def add_datum(self, datum):
        self.node.append(datum.node)


class CreateFrame(CreatePushBase):
    ROOT_NAME = 'create'


class PushFrame(CreatePushBase):
    ROOT_NAME = 'push'


class ClearFrame(BaseFrame):
    ROOT_NAME = 'clear'

    frame = StringField('@frame')


class Stack(XmlObject):
    ROOT_NAME = 'stack'

    def add_frame(self, frame):
        self.node.append(frame.node)


class Assertion(XmlObject):
    ROOT_NAME = 'assert'

    test = StringField('@test')
    text = NodeListField('text', Text)


class Entry(XmlObject):
    ROOT_NAME = 'entry'

    form = StringField('form')
    command = NodeField('command', Command)
    instances = NodeListField('instance', Instance)

    datums = NodeListField('session/datum', SessionDatum)

    stack = NodeField('stack', Stack)

    assertions = NodeListField('assertions/assert', Assertion)


class Menu(DisplayNode, IdNode):
    ROOT_NAME = 'menu'

    root = StringField('@root')
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
    descriptor = StringField('@descriptor')


def get_detail_column_infos(detail, include_sort):
    """
    This is not intented to be a widely used format
    just a packaging of column info into a form most convenient for rendering
    """
    from corehq.apps.app_manager.models import SortElement

    DetailColumnInfo = namedtuple('DetailColumnInfo',
                                  'column sort_element order')
    if not include_sort:
        return [DetailColumnInfo(column, None, None) for column in detail.get_columns()]

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
    sort_only = sorted(sort_elements.items(),
                       key=lambda (field, (sort_element, order)): order)

    for field, (sort_element, order) in sort_only:
        column = create_temp_sort_column(field, len(columns))
        columns.append(DetailColumnInfo(column, sort_element, order))
    return columns


class SuiteGeneratorBase(object):
    descriptor = None
    sections = ()

    def __init__(self, app):
        self.app = app
        # this is actually so slow it's worth caching
        self.modules = list(self.app.get_modules())
        self.id_strings = id_strings

    def generate_suite(self):
        suite = Suite(descriptor=self.descriptor)
        suite.version = self.app.version

        def add_to_suite(attr):
            getattr(suite, attr).extend(getattr(self, attr))

        map(add_to_suite, self.sections)
        return suite.serializeDocument(pretty=True)


class SuiteGenerator(SuiteGeneratorBase):
    descriptor = u"Suite File"
    sections = (
        'xform_resources',
        'locale_resources',
        'details',
        'entries',
        'menus',
        'fixtures',
    )

    @property
    def xform_resources(self):
        first = []
        last = []
        for form_stuff in self.app.get_forms(bare=False):
            form = form_stuff["form"]
            if form_stuff['type'] == 'module_form':
                path = './modules-{module.id}/forms-{form.id}.xml'.format(**form_stuff)
                this_list = first
            else:
                path = './user_registration.xml'
                this_list = last
            resource = XFormResource(
                id=self.id_strings.xform_resource(form),
                version=form.get_version(),
                local=path,
                remote=path,
            )
            if form_stuff['type'] == 'module_form' and self.app.build_version >= '2.9':
                resource.descriptor = u"Form: (Module {module_name}) - {form_name}".format(
                    module_name=trans(form_stuff["module"]["name"], langs=[self.app.default_language]),
                    form_name=trans(form["name"], langs=[self.app.default_language])
                )
            elif path == './user_registration.xml':
                resource.descriptor=u"User Registration Form"
            this_list.append(resource)
        for x in first:
            yield x
        for x in last:
            yield x

    @property
    def locale_resources(self):
        for lang in ["default"] + self.app.build_langs:
            path = './{lang}/app_strings.txt'.format(lang=lang)
            resource = LocaleResource(
                language=lang,
                id=self.id_strings.locale_resource(lang),
                version=self.app.version,
                local=path,
                remote=path,
            )
            if self.app.build_version >= '2.9':
                unknown_lang_txt = u"Unknown Language (%s)" % lang
                resource.descriptor = u"Translations: %s" % languages_mapping().get(lang, [unknown_lang_txt])[0]
            yield resource

    @property
    @memoized
    def details(self):

        r = []
        from corehq.apps.app_manager.detail_screen import get_column_generator
        if not self.app.use_custom_suite:
            for module in self.modules:
                for detail_type, detail, enabled in module.get_details():
                    if enabled:
                        detail_column_infos = get_detail_column_infos(
                            detail,
                            include_sort=detail_type.endswith('short'),
                        )

                        if detail_column_infos:
                            d = Detail(
                                id=self.id_strings.detail(module, detail_type),
                                title=Text(locale_id=self.id_strings.detail_title_locale(module, detail_type))
                            )

                            for column_info in detail_column_infos:
                                fields = get_column_generator(
                                    self.app, module, detail,
                                    detail_type=detail_type, *column_info
                                ).fields
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
        short_detail = module.case_details.short
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

    def get_nodeset_xpath(self, case_type, module, use_filter):
        return "instance('casedb')/casedb/case[@case_type='{case_type}'][@status='open']{filter_xpath}".format(
            case_type=case_type,
            filter_xpath=self.get_filter_xpath(module) if use_filter else '',
        )

    def get_parent_filter(self, relationship, parent_id):
        return "[index/{relationship}=instance('commcaresession')/session/data/{parent_id}]".format(
            relationship=relationship,
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

    @memoized
    def get_detail_ids(self):
        return [detail.id for detail in self.details]

    def get_detail_id_safe(self, module, detail_type):
        detail_id = self.id_strings.detail(
            module=module,
            detail_type=detail_type,
        )
        return detail_id if detail_id in self.get_detail_ids() else None

    @property
    def entries(self):
        # avoid circular dependency
        from corehq.apps.app_manager.models import Module, AdvancedModule

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

                getattr(self, 'configure_entry_{0}'.format(form.form_type))(module, e, form)
                yield e

            if hasattr(module, 'case_list') and module.case_list.show:
                e = Entry(
                    command=Command(
                        id=self.id_strings.case_list_command(module),
                        locale_id=self.id_strings.case_list_locale(module),
                    )
                )
                if isinstance(module, Module):
                    self.configure_entry_module(module, e, use_filter=False)
                elif isinstance(module, AdvancedModule):
                    e.instances.append(Instance(id='casedb', src='jr://instance/casedb'))
                    e.datums.append(SessionDatum(
                        id='case_id_case_%s' % module.case_type,
                        nodeset=(self.get_nodeset_xpath(module.case_type, module, False)),
                        value="./@case_id",
                        detail_select=self.get_detail_id_safe(module, 'case_short'),
                        detail_confirm=self.get_detail_id_safe(module, 'case_long')
                    ))
                    if self.app.commtrack_enabled:
                        e.datums.append(SessionDatum(
                            id='product_id',
                            nodeset="instance('products')/products/product",
                            value="./@id",
                            detail_select=self.get_detail_id_safe(module, 'product_short')
                        ))
                        e.instances.append(Instance(id='products', src='jr://fixture/commtrack:products'))
                        e.instances.append(Instance(id='ledgerdb', src='jr://instance/ledgerdb'))
                yield e

    def get_indicator_instances(self, module, form=None):
        indicator_sets = []
        for _, detail, _ in module.get_details():
            for column in detail.get_columns():
                if column.field_type == FIELD_TYPE_INDICATOR:
                    indicator_set, _ = column.field_property.split('/', 1)
                    if indicator_set not in indicator_sets:
                        indicator_sets.append(indicator_set)
                        yield Instance(id=self.id_strings.indicator_instance(indicator_set),
                                       src='jr://fixture/indicators:%s' % indicator_set)

    def get_location_instances(self, module, form=None):
        # will return an empty list or a list containing the one location instance
        for _, detail, _ in module.get_details():
            for column in detail.get_columns():
                if column.field_type == FIELD_TYPE_LOCATION:
                    return [Instance(id='commtrack:locations',
                                     src='jr://fixture/commtrack:locations')]
        return []

    def get_fixture_instances(self, module, form=None):
        from corehq.apps.app_manager.models import AUTO_SELECT_FIXTURE
        if form and hasattr(form, 'actions'):
            actions = form.actions.auto_select_actions[AUTO_SELECT_FIXTURE]
            fixtures = set([a.auto_select.value_source for a in actions])
            for fixture in fixtures:
                yield Instance(id='{0}s'.format(fixture), src='jr://fixture/item-list:{0}'.format(fixture))

    def get_extra_instances(self, module, form=None):
        for instance in self.get_indicator_instances(module, form):
            yield instance
        for instance in self.get_location_instances(module, form):
            yield instance
        for instance in self.get_fixture_instances(module, form):
            yield instance

    def add_assertion(self, entry, test, locale_id, locale_arguments=None):
        assertion = Assertion(test=test)
        text = Text(locale_id=locale_id)
        if locale_arguments:
            locale = text.locale
            for arg in locale_arguments:
                locale.arguments.append(LocaleArgument(value=arg))
        assertion.text.append(text)
        entry.assertions.append(assertion)

    def add_case_sharing_assertion(self, entry):
        entry.instances.append(Instance(id='groups', src='jr://fixture/user-groups'))
        self.add_assertion(entry, "count(instance('groups')/groups/group) = 1", 'case_sharing.exactly_one_group')

    def add_auto_select_assertion(self, entry, case_id_xpath, mode, locale_arguments=None):
        self.add_assertion(
            entry,
            "{0} = 1".format(case_id_xpath.count()),
            'case_autoload.{0}.property_missing'.format(mode),
            locale_arguments
        )
        case_count = CaseIDXPath(case_id_xpath).case().count()
        self.add_assertion(
            entry,
            "{0} = 1".format(case_count),
            'case_autoload.{0}.case_missing'.format(mode),
        )

    def configure_entry_module_form(self, module, e, form=None, use_filter=True, **kwargs):
        def case_sharing_requires_assertion(form):
            actions = form.active_actions()
            if 'open_case' in actions and autoset_owner_id_for_open_case(actions):
                return True
            if 'subcases' in actions:
                for subcase in actions['subcases']:
                    if autoset_owner_id_for_subcase(subcase):
                        return True
            return False

        if not form or form.requires == 'case':
            self.configure_entry_module(module, e, use_filter=True)

        if form and self.app.case_sharing and case_sharing_requires_assertion(form):
            self.add_case_sharing_assertion(e)

    def configure_entry_module(self, module, e, use_filter=False):
        def get_instances():
            yield Instance(id='casedb', src='jr://instance/casedb')
            if (any(form.form_filter for form in module.get_forms())
                and module.all_forms_require_a_case()) \
                or module.parent_select.active:
                yield Instance(id='commcaresession',
                               src='jr://instance/session')

            for instance in self.get_extra_instances(module):
                yield instance

        e.instances.extend(get_instances())

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
                parent_filter = self.get_parent_filter(module.parent_select.relationship, parent_id)
            e.datums.append(SessionDatum(
                id=datum_ids[i],
                nodeset=(self.get_nodeset_xpath(module.case_type, module, use_filter)
                         + parent_filter),
                value="./@case_id",
                detail_select=self.get_detail_id_safe(module, 'case_short'),
                detail_confirm=(
                    self.get_detail_id_safe(module, 'case_long')
                    if i == 0 else None
                )
            ))

    def configure_entry_advanced_form(self, module, e, form, **kwargs):
        from corehq.apps.app_manager.models import AUTO_SELECT_USER, AUTO_SELECT_CASE, \
            AUTO_SELECT_FIXTURE, AUTO_SELECT_RAW

        def case_sharing_requires_assertion(form):
            actions = form.actions.open_cases
            for action in actions:
                if 'owner_id' in action.case_properties:
                    return True
            return False

        def get_instances():
            yield Instance(id='casedb', src='jr://instance/casedb')

            parent_select = any(action.parent_tag for action in form.actions.load_update_cases)
            form_filter = any(form.form_filter for form in module.get_forms())
            if parent_select or (form_filter and module.all_forms_require_a_case()) or \
                    form.actions.auto_select_actions[AUTO_SELECT_USER] or \
                    form.actions.auto_select_actions[AUTO_SELECT_CASE] or \
                    form.actions.auto_select_actions[AUTO_SELECT_RAW]:
                yield Instance(id='commcaresession', src='jr://instance/session')
            elif module.get_app().commtrack_enabled:
                try:
                    if form.actions.load_update_cases[-1].show_product_stock:
                        yield Instance(id='commcaresession', src='jr://instance/session')
                except IndexError:
                    pass

            for instance in self.get_extra_instances(module, form):
                yield instance

        e.instances.extend(get_instances())

        def get_target_module(case_type, module_id, with_product_details=False):
            if module_id:
                if module_id == module.unique_id:
                    return module

                from corehq.apps.app_manager.models import ModuleNotFoundException
                try:
                    target = module.get_app().get_module_by_unique_id(module_id)
                    if target.case_type != case_type:
                        raise ParentModuleReferenceError(
                            "Module with ID %s has incorrect case type" % module_id
                        )
                    if with_product_details and not hasattr(target, 'product_details'):
                        raise ParentModuleReferenceError(
                            "Module with ID %s has no product details configuration" % module_id
                        )
                    return target
                except ModuleNotFoundException as ex:
                    raise ParentModuleReferenceError(ex.message)
            else:
                if case_type == module.case_type:
                    return module

                target_modules = [mod for mod in module.get_app().modules
                                      if mod.case_type == case_type and
                                         (not with_product_details or hasattr(mod, 'product_details'))]
                try:
                    return target_modules[0]
                except IndexError:
                    raise ParentModuleReferenceError(
                        "Module with case type %s in app %s not found" % (case_type, self.app)
                    )

        for action in form.actions.load_update_cases:
            auto_select = action.auto_select
            if auto_select and auto_select.mode:
                if auto_select.mode == AUTO_SELECT_USER:
                    xpath = session_var(auto_select.value_key, subref='user')
                    e.datums.append(SessionDatum(
                        id=action.case_session_var,
                        function=xpath
                    ))
                    self.add_auto_select_assertion(e, xpath, auto_select.mode, [auto_select.value_key])
                elif auto_select.mode == AUTO_SELECT_CASE:
                    try:
                        ref = form.actions.actions_meta_by_tag[auto_select.value_source]['action']
                        sess_var = ref.case_session_var
                    except KeyError:
                        raise ValueError("Case tag not found: %s" % auto_select.value_source)
                    xpath = CaseIDXPath(session_var(sess_var)).case().index_id(auto_select.value_key)
                    e.datums.append(SessionDatum(
                        id=action.case_session_var,
                        function=xpath
                    ))
                    self.add_auto_select_assertion(e, xpath, auto_select.mode, [auto_select.value_key])
                elif auto_select.mode == AUTO_SELECT_FIXTURE:
                    xpath_base = FixtureXpath(auto_select.value_source).table()
                    xpath = xpath_base.slash(auto_select.value_key)
                    e.datums.append(SessionDatum(
                        id=action.case_session_var,
                        function=xpath
                    ))
                    self.add_assertion(
                        e,
                        "{0} = 1".format(xpath_base.count()),
                        'case_autoload.{0}.exactly_one_fixture'.format(auto_select.mode),
                        [auto_select.value_source]
                    )
                    self.add_auto_select_assertion(e, xpath, auto_select.mode, [auto_select.value_key])
                elif auto_select.mode == AUTO_SELECT_RAW:
                    e.datums.append(SessionDatum(
                        id=action.case_session_var,
                        function=auto_select.value_key
                    ))
            else:
                if action.parent_tag:
                    parent_action = form.actions.actions_meta_by_tag[action.parent_tag]['action']
                    parent_filter = self.get_parent_filter(parent_action.parent_reference_id, parent_action.case_session_var)
                else:
                    parent_filter = ''

                referenced_by = form.actions.actions_meta_by_parent_tag.get(action.case_tag)

                target_module = get_target_module(action.case_type, action.details_module)
                e.datums.append(SessionDatum(
                    id=action.case_session_var,
                    nodeset=(self.get_nodeset_xpath(action.case_type, target_module, False) + parent_filter),
                    value="./@case_id",
                    detail_select=self.get_detail_id_safe(target_module, 'case_short'),
                    detail_confirm=(
                        self.get_detail_id_safe(target_module, 'case_long')
                        if not referenced_by or referenced_by['type'] != 'load' else None
                    )
                ))

        if module.get_app().commtrack_enabled:
            try:
                last_action = form.actions.load_update_cases[-1]
                if last_action.show_product_stock:
                    product_filter = ''
                    if last_action.product_program:
                        product_filter = "[program_id='{}']".format(last_action.product_program)

                    target_module = get_target_module(action.case_type, last_action.details_module, True)
                    e.datums.append(SessionDatum(
                        id='product_id',
                        nodeset="instance('products')/products/product{}".format(product_filter),
                        value="./@id",
                        detail_select=self.get_detail_id_safe(target_module, 'product_short')
                    ))
                    e.instances.append(Instance(id='products', src='jr://fixture/commtrack:products'))
                    e.instances.append(Instance(id='ledgerdb', src='jr://instance/ledgerdb'))
            except IndexError:
                pass

        if self.app.case_sharing and case_sharing_requires_assertion(form):
            self.add_case_sharing_assertion(e)

    def configure_entry_careplan_form(self, module, e, form=None, **kwargs):
            e.instances.append(Instance(id='casedb', src='jr://instance/casedb'))
            e.instances.append(Instance(id='commcaresession', src='jr://instance/session'))

            parent_module = self.get_module_by_id(module.parent_select.module_id)
            e.datums.append(SessionDatum(
                id='case_id',
                nodeset=self.get_nodeset_xpath(parent_module.case_type, parent_module, False),
                value="./@case_id",
                detail_select=self.get_detail_id_safe(parent_module, 'case_short'),
                detail_confirm=self.get_detail_id_safe(parent_module, 'case_long')
            ))

            def session_datum(datum_id, case_type, parent_ref, parent_val):
                nodeset = CaseTypeXpath(case_type).case().select(
                    'index/%s' % parent_ref, session_var(parent_val), quote=False
                ).select('@status', 'open')
                return SessionDatum(
                    id=datum_id,
                    nodeset=nodeset,
                    value="./@case_id",
                    detail_select=self.get_detail_id_safe(module, '%s_short' % case_type),
                    detail_confirm=self.get_detail_id_safe(module, '%s_long' % case_type)
                )

            if form.case_type == CAREPLAN_GOAL:
                e.stack = Stack()
                open_goal = CaseIDXPath(session_var('case_id_goal')).case().select('@status', 'open')
                frame = CreateFrame(
                    if_clause='{count} = 1'.format(count=open_goal.count())
                )
                frame.add_command(self.id_strings.menu(parent_module))
                frame.add_datum(StackDatum(id='case_id', value=session_var('case_id')))
                frame.add_command(self.id_strings.menu(module))
                frame.add_datum(StackDatum(id='case_id_goal', value=session_var('case_id_goal')))
                e.stack.add_frame(frame)

                if form.mode == 'create':
                    e.datums.append(SessionDatum(id='case_id_goal', function='uuid()'))
                elif form.mode == 'update':
                    e.datums.append(session_datum('case_id_goal', CAREPLAN_GOAL, 'parent', 'case_id'))
            elif form.case_type == CAREPLAN_TASK:
                e.stack = Stack()
                frame = CreateFrame()
                frame.add_command(self.id_strings.menu(parent_module))
                frame.add_datum(StackDatum(id='case_id', value=session_var('case_id')))
                frame.add_command(self.id_strings.menu(module))
                frame.add_datum(StackDatum(id='case_id_goal', value=session_var('case_id_goal')))
                e.stack.add_frame(frame)

                if form.mode == 'create':
                    e.datums.append(session_datum('case_id_goal', CAREPLAN_GOAL, 'parent', 'case_id'))
                elif form.mode == 'update':
                    e.datums.append(session_datum('case_id_goal', CAREPLAN_GOAL, 'parent', 'case_id'))
                    e.datums.append(session_datum('case_id_task', CAREPLAN_TASK, 'goal', 'case_id_goal'))

                    count = CaseTypeXpath(CAREPLAN_TASK).case().select(
                        'index/goal', session_var('case_id_goal'), quote=False
                    ).select('@status', 'open').count()
                    frame.if_clause = '{count} >= 1'.format(count=count)

                    frame.add_command(self.id_strings.form_command(module.get_form_by_type(CAREPLAN_TASK, 'update')))

    @property
    def menus(self):
        # avoid circular dependency
        from corehq.apps.app_manager.models import CareplanModule, AdvancedForm
        for module in self.modules:
            if isinstance(module, CareplanModule):
                update_menu = Menu(
                    id=self.id_strings.menu(module),
                    locale_id=self.id_strings.module_locale(module),
                )

                if not module.display_separately:
                    parent = self.get_module_by_id(module.parent_select.module_id)
                    create_goal_form = module.get_form_by_type(CAREPLAN_GOAL, 'create')
                    create_menu = Menu(
                        id=self.id_strings.menu(parent),
                        locale_id=self.id_strings.module_locale(parent),
                    )
                    create_menu.commands.append(Command(id=self.id_strings.form_command(create_goal_form)))
                    yield create_menu

                    update_menu.root = self.id_strings.menu(parent)
                else:
                    update_menu.commands.extend([
                        Command(id=self.id_strings.form_command(module.get_form_by_type(CAREPLAN_GOAL, 'create'))),
                    ])

                update_menu.commands.extend([
                    Command(id=self.id_strings.form_command(module.get_form_by_type(CAREPLAN_GOAL, 'update'))),
                    Command(id=self.id_strings.form_command(module.get_form_by_type(CAREPLAN_TASK, 'create'))),
                    Command(id=self.id_strings.form_command(module.get_form_by_type(CAREPLAN_TASK, 'update'))),
                ])
                yield update_menu
            else:
                menu = Menu(
                    id=self.id_strings.menu(module),
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
                            if isinstance(form, AdvancedForm):
                                try:
                                    var = form.actions.load_update_cases[-1].case_session_var
                                    case = CaseIDXPath(session_var(var)).case()
                                except IndexError:
                                    case = None
                            else:
                                case = SESSION_CASE_ID.case()

                            if case:
                                command.relevant = dot_interpolate(form.form_filter, case)
                        yield command

                    if hasattr(module, 'case_list') and module.case_list.show:
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


class MediaSuiteGenerator(SuiteGeneratorBase):
    descriptor = u"Media Suite File"
    sections = ('media_resources',)

    @property
    def media_resources(self):
        PREFIX = 'jr://file/'
        # you have to call remove_unused_mappings
        # before iterating through multimedia_map
        self.app.remove_unused_mappings()
        if self.app.multimedia_map is None:
            self.app.multimedia_map = {}
        for path, m in self.app.multimedia_map.items():
            unchanged_path = path
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

            if not getattr(m, 'unique_id', None):
                # lazy migration for adding unique_id to map_item
                m.unique_id = HQMediaMapItem.gen_unique_id(m.multimedia_id, unchanged_path)

            yield MediaResource(
                id=self.id_strings.media_resource(m.unique_id, name),
                path=path,
                version=m.version,
                local=None,
                remote=get_url_base() + reverse(
                    'hqmedia_download',
                    args=[m.media_type, m.multimedia_id]
                ) + urllib.quote(name.encode('utf-8')) if name else name
            )


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
