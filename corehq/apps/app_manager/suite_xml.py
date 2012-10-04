from lxml import etree
from eulxml.xmlmap import StringField, XmlObject, IntegerField, NodeListField, NodeField, StringListField

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

class AbstractResource(XmlObject):

    LOCATION_TEMPLATE = 'resource/location[@authority="%s"]'

    local = StringField(LOCATION_TEMPLATE % 'local', required=True)
    remote = StringField(LOCATION_TEMPLATE % 'remote', required=True)

    version = IntegerField('resource/@version')
    id = StringField('resource/@id')

    def __init__(self, id=None, version=None, local=None, remote=None, **kwargs):
        super(AbstractResource, self).__init__(**kwargs)
        self.id = id
        self.version = version
        self.local = local
        self.remote = remote

class XFormResource(AbstractResource):
    ROOT_NAME = 'xform'

class LocaleResource(AbstractResource):
    ROOT_NAME = 'locale'
    language = StringField('@language')

class Display(XmlObject):
    ROOT_NAME = 'display'
    text = NodeField('text', Text)
    media_image = StringField('media/@image')
    media_audio = StringField('media/@audio')

    def __init__(self, text=None, media_image=None, media_audio=None, **kwargs):
        super(Display, self).__init__(text=text, **kwargs)
        self.media_image = media_image
        self.media_audio = media_audio

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


class Instance(IdNode):
    ROOT_NAME = 'instance'

    src = StringField('@src')

    def __init__(self, id=None, src=None, **kwargs):
        super(Instance, self).__init__(id=id, **kwargs)
        self.src = src

class SessionDatum(IdNode):
    ROOT_NAME = 'datum'

    nodeset = StringField('@nodeset')
    value = StringField('@value')
    detail_select = StringField('@detail-select')
    detail_confirm = StringField('@detail-confirm')

class Entry(XmlObject):
    ROOT_NAME = 'entry'

    form = StringField('form')
    command = NodeField('command', Command)
    instance = NodeField('instance', Instance)

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

class Field(XmlObject):
    ROOT_NAME = 'field'

    sort = StringField('@sort')
    header = NodeField('header', Header)
    template = NodeField('template', Template)

class DetailVariable(XmlObject):
    ROOT_NAME = '_'
    function = StringField('@function')

    def get_name(self):
        return self.node.tag

    def set_name(self, value):
        self.node.tag = value

    name = property(get_name, set_name)

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
    variables = NodeListField('variables/*', DetailVariable)
    fields = NodeListField('field', Field)


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

    details = NodeListField('detail', Detail)
    entries = NodeListField('entry', Entry)
    menus = NodeListField('menu', Menu)

    fixtures = NodeListField('fixture', Fixture)

class IdStrings(object):

    def xform_resource(self, form):
        return form.unique_id

    def locale_resource(self, lang):
        return u'app_{lang}_strings'.format(lang=lang)

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

class SuiteGenerator(object):
    def __init__(self, app):
        self.app = app
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
                version=self.app.version,
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
    def details(self):
        from corehq.apps.app_manager.detail_screen import get_column_generator
        if not self.app.use_custom_suite:
            for module in self.app.get_modules():
                for detail in module.get_details():
                    detail_columns = detail.get_columns()
                    if detail_columns and detail.type in ('case_short', 'case_long'):
                        d = Detail(
                            id=self.id_strings.detail(module, detail),
                            title=Text(locale_id=self.id_strings.detail_title_locale(module, detail))
                        )
                        for column in detail_columns:
                            fields = get_column_generator(self.app, module, detail, column).fields
                            d.fields.extend(fields)
                        try:
                            d.fields[0].sort = 'default'
                        except IndexError:
                            pass
                        else:
                            # only yield the Detail if it has Fields
                            yield d

    def get_filter_xpath(self, module):
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
        return xpath

    @property
    def entries(self):
        """
        {% for module in app.get_modules %}
          {% for form in module.get_forms %}
            ---
          {% endfor %}
          {% if module.case_list.show %}
            <entry>
                <command id="m{{ module.id }}-case-list">
                    <text><locale id="case_lists.m{{ module.id }}"/></text>
                </command>
                <instance id="casedb" src="jr://instance/casedb"/>
                <session>
                    <datum id="case_id" nodeset="instance('casedb')/casedb/case[@case_type='{{ module.case_type }}'][@status='open']" value="./@case_id" detail-select="m{{ module.id }}_case_short" detail-confirm="m{{ module.id }}_case_long"/>
                </session>
            </entry>
          {% endif %}
         {% endfor %}
        """
        def add_case_stuff(module, e, use_filter=False):
            e.instance = Instance(id='casedb', src='jr://instance/casedb')
            # I'm setting things individually instead of in the constructor so they appear in the correct order
            e.datum = SessionDatum()
            e.datum.id='case_id'
            e.datum.nodeset="instance('casedb')/casedb/case[@case_type='{module.case_type}'][@status='open']{filter_xpath}".format(
                module=module,
                filter_xpath=self.get_filter_xpath(module) if use_filter else None
            )
            e.datum.value="./@case_id"
            e.datum.detail_select=self.id_strings.detail(module=module, detail=module.get_detail('case_short'))
            e.datum.detail_confirm=self.id_strings.detail(module=module, detail=module.get_detail('case_long'))

        for module in self.app.get_modules():
            for form in module.get_forms():
                e = Entry()
                e.form = form.xmlns
                e.command=Command(
                    id=form.get_command_id(),
                    locale_id=form.get_locale_id(),
                    media_image=form.media_image,
                    media_audio=form.media_audio,
                )
                if form.requires == "case":
                    add_case_stuff(module, e, use_filter=True)
                yield e
            if module.case_list.show:
                e = Entry(
                    command=Command(
                        id=module.get_case_list_command_id(),
                        locale_id=module.get_case_list_locale_id(),
                    )
                )
                add_case_stuff(module, e, use_filter=False)
                yield e
    @property
    def menus(self):
        for module in self.app.get_modules():
            menu = Menu(
                id='root' if module.put_in_root else self.id_strings.menu(module),
                locale_id=module.get_locale_id(),
                media_image=module.media_image,
                media_audio=module.media_audio,
            )

            def get_commands():
                for form in module.get_forms():
                    yield Command(id=form.get_command_id())

                if module.case_list.show:
                    yield Command(id=module.get_case_list_command_id())

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

    def __call__(self, *args, **kwargs):
        suite = Suite()
        suite.version = self.app.version
        def add_to_suite(attr):
            getattr(suite, attr).extend(getattr(self, attr))
        map(add_to_suite, [
            'xform_resources',
            'locale_resources',
            'details',
            'entries',
            'menus',
            'fixtures'
        ])
        return suite.serializeDocument()

def generate_suite(app):
    g = SuiteGenerator(app)
    return g()