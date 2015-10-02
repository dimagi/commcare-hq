from eulxml.xmlmap import (
    StringField, XmlObject, IntegerField, NodeListField,
    NodeField, load_xmlobject_from_string
)
from lxml import etree


class XPathField(StringField):
    """
    A string field that is supposed to contain an arbitrary xpath expression

    """
    pass


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
    function = XPathField('@function')
    variables = NodeListField('variable', XpathVariable)


class LocaleArgument(XmlObject):
    ROOT_NAME = 'argument'
    key = StringField('@key')
    value = StringField('.')


class Id(XmlObject):
    ROOT_NAME = 'id'
    xpath = NodeField('xpath', Xpath)


class Locale(XmlObject):
    ROOT_NAME = 'locale'
    id = StringField('@id')
    child_id = NodeField('id', Id)
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
    xpath_function = XPathField('xpath/@function')

    locale = NodeField('locale', Locale)
    locale_id = StringField('locale/@id')


class ConfigurationItem(Text):
    ROOT_NAME = "text"
    id = StringField("@id")


class ConfigurationGroup(XmlObject):
    ROOT_NAME = 'configuration'
    configs = NodeListField('text', ConfigurationItem)


class Series(OrderedXmlObject):
    ORDER = (
        "configuration",
        "x_function",
        "y_function",
        "radius_function",
    )
    ROOT_NAME = 'series'

    nodeset = StringField('@nodeset')
    configuration = NodeField('configuration', ConfigurationGroup)
    x_function = StringField('x/@function')
    y_function = StringField('y/@function')
    radius_function = StringField("radius/@function")


class Annotation(OrderedXmlObject):
    ORDER = ("x", "y", "text")
    ROOT_NAME = 'annotation'

    # TODO: Specify the xpath without specifying "text" for the child (we want the Text class to specify the tag)
    x = NodeField('x/text', Text)
    y = NodeField('y/text', Text)
    text = NodeField('text', Text)


class Graph(XmlObject):
    ROOT_NAME = 'graph'

    type = StringField("@type", choices=["xy", "bubble"])
    series = NodeListField('series', Series)
    configuration = NodeField('configuration', ConfigurationGroup)
    annotations = NodeListField('annotation', Annotation)


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
    """
    Mixin for any node that has the awkward text-or-display subnode,
    like Command or Menu

    """
    text = NodeField('text', Text)
    display = NodeField('display', Display)

    def __init__(self, node=None, context=None,
                 locale_id=None, media_image=None, media_audio=None, **kwargs):
        super(DisplayNode, self).__init__(node, context, **kwargs)
        self.set_display(
            locale_id=locale_id,
            media_image=media_image,
            media_audio=media_audio,
        )

    def set_display(self, locale_id=None, media_image=None, media_audio=None):
        text = Text(locale_id=locale_id) if locale_id else None

        if media_image or media_audio:
            self.display = Display(
                text=text,
                media_image=media_image,
                media_audio=media_audio,
            )
        elif text:
            self.text = text


class LocaleId(XmlObject):
    ROOT_NAME = 'locale'
    locale_id = StringField('@id')


class MediaText(XmlObject):
    ROOT_NAME = 'text'
    form_name = StringField('@form', choices=['image', 'audio'])  # Nothing XForm-y about this 'form'
    locale = NodeField('locale', LocaleId)


class LocalizedMediaDisplay(XmlObject):
    ROOT_NAME = 'display'

    media_text = NodeListField('text', MediaText)


class TextOrDisplay(XmlObject):
    text = NodeField('text', Text)
    display = NodeField('display', LocalizedMediaDisplay)

    def __init__(self, node=None, context=None,
                 menu_locale_id=None, image_locale_id=None, audio_locale_id=None,
                 media_image=None, media_audio=None, for_action_menu=False, **kwargs):
        super(TextOrDisplay, self).__init__(node, context, **kwargs)
        text = Text(locale_id=menu_locale_id) if menu_locale_id else None

        media_text = []
        if media_image:
            media_text.append(MediaText(
                locale=LocaleId(locale_id=image_locale_id),
                form_name='image',
            ))
        if media_audio:
            media_text.append(MediaText(
                locale=LocaleId(locale_id=audio_locale_id),
                form_name='audio'
            ))

        if media_text:
            self.display = LocalizedMediaDisplay(
                media_text=[text] + media_text if text else media_text
            )
        elif for_action_menu and text:
            self.display = LocalizedMediaDisplay(
                media_text=[text]
            )
        elif text:
            self.text = text


class CommandMixin(XmlObject):
    ROOT_NAME = 'command'
    relevant = StringField('@relevant')


class LocalizedCommand(CommandMixin, TextOrDisplay, IdNode):
    """
        For CC >= 2.21
    """
    pass


class Command(CommandMixin, DisplayNode, IdNode):
    """
        For CC < 2.21
    """
    pass


class Instance(IdNode, OrderedXmlObject):
    ROOT_NAME = 'instance'
    ORDER = ('id', 'src')

    src = StringField('@src')


class SessionDatum(IdNode, OrderedXmlObject):
    ROOT_NAME = 'datum'
    ORDER = (
        'id', 'nodeset', 'value', 'function',
        'detail_select', 'detail_confirm', 'detail_persistent', 'detail_inline'
    )

    nodeset = XPathField('@nodeset')
    value = StringField('@value')
    function = XPathField('@function')
    detail_select = StringField('@detail-select')
    detail_confirm = StringField('@detail-confirm')
    detail_persistent = StringField('@detail-persistent')
    detail_inline = StringField('@detail-inline')


class StackDatum(IdNode):
    ROOT_NAME = 'datum'

    value = XPathField('@value')


class StackCommand(XmlObject):
    ROOT_NAME = 'command'

    value = XPathField('@value')
    command = StringField('.')


class BaseFrame(XmlObject):
    if_clause = XPathField('@if')


class CreatePushBase(IdNode, BaseFrame):

    datums = NodeListField('datum', StackDatum)
    commands = NodeListField('command', StackCommand)

    def add_command(self, command):
        node = etree.SubElement(self.node, 'command')
        node.attrib['value'] = command

    def add_datum(self, datum):
        self.node.append(datum.node)


class CreateFrame(CreatePushBase):
    ROOT_NAME = 'create'


class PushFrame(CreatePushBase):
    ROOT_NAME = 'push'


class ClearFrame(BaseFrame):
    ROOT_NAME = 'clear'

    frame = StringField('@frame')


FRAME_CLASSES = (CreateFrame, PushFrame, ClearFrame)
FRAME_CLASSES_BY_ROOT = {frame_type.ROOT_NAME: frame_type
                         for frame_type in FRAME_CLASSES}


def _wrap_frame(frame):
    return FRAME_CLASSES_BY_ROOT[frame.tag](frame)


class Stack(XmlObject):
    ROOT_NAME = 'stack'

    frames = NodeListField('*', _wrap_frame)

    def add_frame(self, frame):
        self.node.append(frame.node)


class Assertion(XmlObject):
    ROOT_NAME = 'assert'

    test = XPathField('@test')
    text = NodeListField('text', Text)


class Entry(OrderedXmlObject, XmlObject):
    ROOT_NAME = 'entry'
    ORDER = ('form', 'command', 'instance', 'datums')

    form = StringField('form')
    command = NodeField('command', Command)
    instances = NodeListField('instance', Instance)

    datums = NodeListField('session/datum', SessionDatum)

    stack = NodeField('stack', Stack)

    assertions = NodeListField('assertions/assert', Assertion)

    def require_instance(self, *instances):
        used = {(instance.id, instance.src) for instance in self.instances}
        for instance in instances:
            if (instance.id, instance.src) not in used:
                self.instances.append(
                    # it's important to make a copy,
                    # since these can't be reused
                    Instance(id=instance.id, src=instance.src)
                )
                # make sure the first instance gets inserted
                # right after the command
                # once you "suggest" a placement to eulxml,
                # it'll follow your lead and place the rest of them there too
                if len(self.instances) == 1:
                    instance_node = self.node.find('instance')
                    command_node = self.node.find('command')
                    self.node.remove(instance_node)
                    self.node.insert(self.node.index(command_node) + 1,
                                     instance_node)
        sorted_instances = sorted(self.instances,
                                  key=lambda instance: instance.id)
        if sorted_instances != self.instances:
            self.instances = sorted_instances


class MenuMixin(XmlObject):
    ROOT_NAME = 'menu'

    root = StringField('@root')
    relevant = XPathField('@relevant')
    commands = NodeListField('command', Command)


class Menu(MenuMixin, DisplayNode, IdNode):
    """
        For CC < 2.21
    """
    pass


class LocalizedMenu(MenuMixin, TextOrDisplay, IdNode):
    """
        For CC >= 2.21
    """
    pass


class AbstractTemplate(XmlObject):
    form = StringField('@form', choices=['image', 'phone', 'address'])
    width = IntegerField('@width')
    text = NodeField('text', Text)


class Template(AbstractTemplate):
    ROOT_NAME = 'template'


class GraphTemplate(Template):
    # TODO: Is there a way to specify a default/static value for form?
    form = StringField('@form', choices=['graph'])
    graph = NodeField('graph', Graph)


class Header(AbstractTemplate):
    ROOT_NAME = 'header'


class Sort(AbstractTemplate):
    ROOT_NAME = 'sort'

    type = StringField('@type')
    order = StringField('@order')
    direction = StringField('@direction')


class Style(XmlObject):
    ROOT_NAME = 'style'

    horz_align = StringField("@horz-align")
    vert_align = StringField("@vert-align")
    font_size = StringField("@font-size")
    css_id = StringField("@css-id")
    grid_height = StringField("grid/@grid-height")
    grid_width = StringField("grid/@grid-width")
    grid_x = StringField("grid/@grid-x")
    grid_y = StringField("grid/@grid-y")


class Extra(XmlObject):
    ROOT_NAME = 'extra'

    key = StringField("@key")
    value = StringField("@value")


class Response(XmlObject):
    ROOT_NAME = 'response'

    key = StringField("@key")


class Lookup(XmlObject):
    ROOT_NAME = 'lookup'

    name = StringField("@name")
    action = StringField("@action", required=True)
    image = StringField("@image")
    extras = NodeListField('extra', Extra)
    responses = NodeListField('response', Response)


class Field(OrderedXmlObject):
    ROOT_NAME = 'field'
    ORDER = ('header', 'template', 'sort_node')

    sort = StringField('@sort')
    style = NodeField('style', Style)
    header = NodeField('header', Header)
    template = NodeField('template', Template)
    sort_node = NodeField('sort', Sort)
    background = NodeField('background/text', Text)


class ActionMixin(OrderedXmlObject):
    ROOT_NAME = 'action'
    ORDER = ('display', 'stack')

    stack = NodeField('stack', Stack)


class Action(ActionMixin):
    """ For CC < 2.21 """

    display = NodeField('display', Display)


class LocalizedAction(ActionMixin, TextOrDisplay):
    """ For CC >= 2.21 """
    pass


class DetailVariable(XmlObject):
    ROOT_NAME = '_'
    function = XPathField('@function')

    def get_name(self):
        return self.node.tag

    def set_name(self, value):
        self.node.tag = value

    name = property(get_name, set_name)


class DetailVariableList(XmlObject):
    ROOT_NAME = 'variables'

    variables = NodeListField('_', DetailVariable)


class Detail(OrderedXmlObject, IdNode):
    """
    <detail id="">
        <title><text/></title>
        <lookup action="" image="" name="">
            <extra key="" value = "" />
            <response key ="" />
        </lookup>
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
    ORDER = ('title', 'lookup', 'details', 'fields')

    nodeset = StringField('@nodeset')

    title = NodeField('title/text', Text)
    lookup = NodeField('lookup', Lookup)
    fields = NodeListField('field', Field)
    action = NodeField('action', Action)
    details = NodeListField('detail', "self")
    _variables = NodeField('variables', DetailVariableList)

    def get_all_fields(self):
        '''
        Return all fields under this Detail instance and all fields under
        any details that may be under this instance.
        :return:
        '''
        all_fields = []
        for detail in [self] + list(self.details):
            all_fields.extend(list(detail.fields))
        return all_fields

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

    def get_all_xpaths(self):
        result = set()
        if self._variables:
            for variable in self.variables:
                result.add(variable.function)

        if self.action:
            for frame in self.action.stack.frames:
                result.add(frame.if_clause)
                for datum in getattr(frame, 'datums', []):
                    result.add(datum.value)

        for field in self.get_all_fields():
            if field.template.form == 'graph':
                s = etree.tostring(field.template.node)
                template = load_xmlobject_from_string(s, xmlclass=GraphTemplate)
                for series in template.graph.series:
                    result.add(series.nodeset)
            else:
                result.add(field.header.text.xpath_function)
                result.add(field.template.text.xpath_function)

        result.discard(None)
        return result


class Fixture(IdNode):
    ROOT_NAME = 'fixture'

    user_id = StringField('@user_id')

    def set_content(self, xml):
        for child in self.node:
            self.node.remove(child)
        self.node.append(xml)


class ScheduleFixtureVisit(IdNode):
    ROOT_NAME = 'visit'

    due = IntegerField('@due')
    starts = IntegerField('@starts')
    expires = IntegerField('@expires')

    repeats = StringField('@repeats')
    increment = IntegerField('@increment')


class Schedule(XmlObject):
    ROOT_NAME = 'schedule'

    starts = IntegerField('@starts')
    expires = IntegerField('@expires')
    allow_unscheduled = StringField('@allow_unscheduled')

    visits = NodeListField('visit', ScheduleFixtureVisit)


class ScheduleFixture(Fixture):
    schedule = NodeField('schedule', Schedule)


class Suite(OrderedXmlObject):
    ROOT_NAME = 'suite'
    ORDER = ('version', 'descriptor')

    version = IntegerField('@version')
    descriptor = StringField('@descriptor')

    xform_resources = NodeListField('xform', XFormResource)
    locale_resources = NodeListField('locale', LocaleResource)
    media_resources = NodeListField('locale', MediaResource)

    details = NodeListField('detail', Detail)
    entries = NodeListField('entry', Entry)
    menus = NodeListField('menu', Menu)

    fixtures = NodeListField('fixture', Fixture)
