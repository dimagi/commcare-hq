from eulxml.xmlmap import (
    IntegerField,
    NodeField,
    NodeListField,
    SimpleBooleanField,
    StringField,
    XmlObject,
    load_xmlobject_from_string,
)
from lxml import etree

from corehq.apps.app_manager.exceptions import UnknownInstanceError


class XPathField(StringField):
    """
    A string field that is supposed to contain an arbitrary xpath expression

    """
    pass


class BooleanField(SimpleBooleanField):
    def __init__(self, xpath, *args, **kwargs):
        return super().__init__(xpath, 'true', 'false', *args, **kwargs)


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


class CalculatedPropertyXpathVariable(XmlObject):
    ROOT_NAME = 'variable'
    name = StringField('@name')
    locale_id = StringField('locale/@id')


class CalculatedPropertyXpath(XmlObject):
    ROOT_NAME = 'xpath'
    function = XPathField('@function')
    variables = NodeListField('variable', CalculatedPropertyXpathVariable)


class XpathVariable(XmlObject):
    ROOT_NAME = 'variable'
    name = StringField('@name')

    locale_id = StringField('locale/@id')
    xpath = NodeField('xpath', CalculatedPropertyXpath)

    @property
    def value(self):
        return self.locale_id or self.xpath


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


class XpathEnum(Xpath):
    @classmethod
    def build(cls, enum, template, get_template_context, get_value):
        variables = []
        for item in enum:
            v_key = item.key_as_variable
            v_val = get_value(v_key)
            variables.append(XpathVariable(name=v_key, locale_id=v_val))

        parts = []
        for i, item in enumerate(enum):
            template_context = get_template_context(item, i)
            parts.append(template.format(**template_context))
        parts.append("''")
        parts.append(")" * len(enum))
        function = ''.join(parts)

        return cls(
            function=function,
            variables=variables,
        )


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

    type = StringField("@type", choices=["xy", "bubble", "bar", "time"])
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


class ReleaseInfoXFormResource(AbstractResource):
    ROOT_NAME = 'xform-update-info'


class LocaleResource(AbstractResource):
    ROOT_NAME = 'locale'
    language = StringField('@language')


class MediaResource(AbstractResource):
    ROOT_NAME = 'media'
    path = StringField('@path')
    lazy = BooleanField('resource/@lazy')


class PracticeUserRestoreResource(AbstractResource):
    ROOT_NAME = 'user-restore'


class Display(OrderedXmlObject):
    ROOT_NAME = 'display'
    ORDER = ('text', 'media_image', 'media_audio', 'hint')
    text = NodeField('text', Text)
    media_image = StringField('media/@image')
    media_audio = StringField('media/@audio')
    hint = NodeField('hint', 'self')


class Hint(Display):
    ROOT_NAME = 'hint'


class Itemset(XmlObject):
    ROOT_NAME = 'itemset'
    nodeset = StringField('@nodeset')
    value_ref = StringField('value/@ref')
    label_ref = StringField('label/@ref')
    sort_ref = StringField('sort/@ref')


class DisplayNode(XmlObject):
    """
    Mixin for any node that has the awkward text-or-display subnode,
    like Command or Menu

    """
    text = NodeField('text', Text)
    display = NodeField('display', Display)

    def __init__(self, node=None, context=None, locale_id=None,
                 media_image=None, media_audio=None, **kwargs):
        super(DisplayNode, self).__init__(node, context, **kwargs)
        self.set_display(
            locale_id=locale_id,
            media_image=media_image,
            media_audio=media_audio,
        )

    def set_display(self, locale_id=None, media_image=None, media_audio=None):
        text = None
        if locale_id:
            text = Text(locale_id=locale_id)

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
    xpath = NodeField('xpath', Xpath)
    xpath_function = XPathField('xpath/@function')


class LocalizedMediaDisplay(XmlObject):
    ROOT_NAME = 'display'

    media_text = NodeListField('text', MediaText)


class TextOrDisplay(XmlObject):
    text = NodeField('text', Text)
    display = NodeField('display', LocalizedMediaDisplay)

    def __init__(self, node=None, context=None, custom_icon_locale_id=None, custom_icon_form=None,
                 custom_icon_xpath=None, menu_locale_id=None, image_locale_id=None,
                 audio_locale_id=None, media_image=None, media_audio=None, for_action_menu=False, **kwargs):
        super(TextOrDisplay, self).__init__(node, context, **kwargs)
        text = None
        if menu_locale_id:
            text = Text(locale_id=menu_locale_id)

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

        if (custom_icon_locale_id or custom_icon_xpath) and custom_icon_form:
            media_text.append(MediaText(
                locale=(LocaleId(locale_id=custom_icon_locale_id) if custom_icon_locale_id else None),
                xpath_function=(custom_icon_xpath if custom_icon_xpath else None),
                form_name=custom_icon_form
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

    def __eq__(self, other):
        return self.src == other.src and self.id == other.id

    def __hash__(self):
        return hash((self.src, self.id))


class SessionDatum(IdNode, OrderedXmlObject):
    ROOT_NAME = 'datum'
    ORDER = (
        'id', 'nodeset', 'value', 'function',
        'detail_select', 'detail_confirm', 'detail_persistent', 'detail_inline',
        'autoselect',
    )

    nodeset = XPathField('@nodeset')
    value = StringField('@value')
    function = XPathField('@function')
    detail_select = StringField('@detail-select')
    detail_confirm = StringField('@detail-confirm')
    detail_persistent = StringField('@detail-persistent')
    detail_inline = StringField('@detail-inline')
    autoselect = BooleanField('@autoselect')


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

    def add_mark(self):
        etree.SubElement(self.node, 'mark')

    def add_rewind(self, rewind_value):
        node = etree.SubElement(self.node, 'rewind')
        node.attrib['value'] = rewind_value


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


class Argument(IdNode):
    ROOT_NAME = 'argument'


class SessionEndpoint(IdNode):
    ROOT_NAME = 'endpoint'

    command_id = StringField('@command_id')
    arguments = NodeListField('argument', Argument)
    stack = NodeField('stack', Stack)


class Assertion(XmlObject):
    ROOT_NAME = 'assert'

    test = XPathField('@test')
    text = NodeListField('text', Text)


class QueryData(XmlObject):
    ROOT_NAME = 'data'

    key = StringField('@key')
    ref = XPathField('@ref')


class QueryPrompt(DisplayNode):
    ROOT_NAME = 'prompt'

    key = StringField('@key')
    appearance = StringField('@appearance', required=False)
    receive = StringField('@receive', required=False)
    hidden = BooleanField('@hidden', required=False)
    input_ = StringField('@input', required=False)
    default_value = StringField('@default', required=False)
    allow_blank_value = BooleanField('@allow_blank_value', required=False)

    itemset = NodeField('itemset', Itemset)


class RemoteRequestQuery(OrderedXmlObject, XmlObject):
    ROOT_NAME = 'query'
    ORDER = ('data', 'prompts')

    url = StringField('@url')
    storage_instance = StringField('@storage-instance')
    template = StringField('@template')
    data = NodeListField('data', QueryData)
    prompts = NodeListField('prompt', QueryPrompt)
    default_search = BooleanField("@default_search")


class Entry(OrderedXmlObject, XmlObject):
    ROOT_NAME = 'entry'
    ORDER = ('form', 'command', 'instance', 'datums')

    form = StringField('form')
    command = NodeField('command', Command)
    instances = NodeListField('instance', Instance)

    datums = NodeListField('session/datum', SessionDatum)
    queries = NodeListField('session/query', RemoteRequestQuery)

    stack = NodeField('stack', Stack)

    assertions = NodeListField('assertions/assert', Assertion)

    def require_instances(self, instances=(), instance_ids=()):
        used = {(instance.id, instance.src) for instance in self.instances}
        for instance in instances:
            if 'remote' in instance.src:
                continue
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
        covered_ids = {instance_id for instance_id, _ in used}
        for instance_id in instance_ids:
            if instance_id not in covered_ids:
                raise UnknownInstanceError(
                    "Instance reference not recognized: {} in xpath \"{}\""
                    # to get xpath context to show in this error message
                    # make instance_id a unicode subclass with an xpath property
                    .format(instance_id, getattr(instance_id, 'xpath', "(Xpath Unknown)")))

        sorted_instances = sorted(self.instances,
                                  key=lambda instance: instance.id)
        if sorted_instances != self.instances:
            self.instances = sorted_instances


class RemoteRequestPost(XmlObject):
    ROOT_NAME = 'post'

    url = StringField('@url')
    relevant = StringField('@relevant')
    data = NodeListField('data', QueryData)


class RemoteRequestSession(OrderedXmlObject, XmlObject):
    ROOT_NAME = 'session'
    ORDER = ('queries', 'data')

    queries = NodeListField('query', RemoteRequestQuery)
    data = NodeListField('datum', SessionDatum)


class RemoteRequest(OrderedXmlObject, XmlObject):
    """
    Used to set the URL and query details for synchronous search.

    See "remote-request" in the `CommCare 2.0 Suite Definition`_ for details.


    .. _CommCare 2.0 Suite Definition: https://github.com/dimagi/commcare/wiki/Suite20#remote-request

    """
    ROOT_NAME = 'remote-request'
    ORDER = ('post', 'command', 'instances', 'session', 'stack')

    post = NodeField('post', RemoteRequestPost)
    instances = NodeListField('instance', Instance)
    command = NodeField('command', Command)
    session = NodeField('session', RemoteRequestSession)
    stack = NodeField('stack', Stack)


class MenuMixin(XmlObject):
    ROOT_NAME = 'menu'

    root = StringField('@root')
    relevant = XPathField('@relevant')
    style = StringField('@style')
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

    @classmethod
    def build(cls, form, graph, locale_config=None, locale_series_config=None, locale_annotation=None):
        return cls(
            form=form,
            graph=Graph(
                type=graph.graph_type,
                series=[
                    Series(
                        nodeset=s.data_path,
                        x_function=s.x_function,
                        y_function=s.y_function,
                        radius_function=s.radius_function,
                        configuration=ConfigurationGroup(
                            configs=(
                                [
                                    # TODO: It might be worth wrapping
                                    #       these values in quotes (as appropriate)
                                    #       to prevent the user from having to
                                    #       figure out why their unquoted colors
                                    #       aren't working.
                                    ConfigurationItem(id=k, xpath_function=v)
                                    for k, v in s.config.items()
                                ] + [
                                    ConfigurationItem(id=k, locale_id=locale_series_config(index, k))
                                    for k, v in sorted(s.locale_specific_config.items())
                                ]
                            )
                        )
                    )
                    for index, s in enumerate(graph.series)],
                configuration=ConfigurationGroup(
                    configs=(
                        [
                            ConfigurationItem(id=k, xpath_function=v)
                            for k, v
                            in graph.config.items()
                        ] + [
                            ConfigurationItem(id=k, locale_id=locale_config(k))
                            for k, v
                            in graph.locale_specific_config.items()
                        ]
                    )
                ),
                annotations=[
                    Annotation(
                        x=Text(xpath_function=a.x),
                        y=Text(xpath_function=a.y),
                        text=Text(locale_id=locale_annotation(i))
                    )
                    for i, a in enumerate(
                        graph.annotations
                    )]
            )
        )


class Header(AbstractTemplate):
    ROOT_NAME = 'header'


class Sort(AbstractTemplate):
    ROOT_NAME = 'sort'

    type = StringField('@type')
    order = StringField('@order')
    direction = StringField('@direction')
    blanks = StringField('@blanks')


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


class Field(OrderedXmlObject):
    ROOT_NAME = 'field'
    ORDER = ('header', 'template', 'sort_node')

    sort = StringField('@sort')
    print_id = StringField('@print-id')
    style = NodeField('style', Style)
    header = NodeField('header', Header)
    template = NodeField('template', Template)
    sort_node = NodeField('sort', Sort)
    background = NodeField('background/text', Text)


class Lookup(OrderedXmlObject):
    ROOT_NAME = 'lookup'
    ORDER = ('auto_launch', 'extras', 'responses', 'field')

    name = StringField("@name")
    auto_launch = BooleanField("@auto_launch")
    action = StringField("@action", required=True)
    image = StringField("@image")
    extras = NodeListField('extra', Extra)
    responses = NodeListField('response', Response)
    field = NodeField('field', Field)


class ActionMixin(OrderedXmlObject):
    ROOT_NAME = 'action'
    ORDER = ('display', 'stack')

    stack = NodeField('stack', Stack)
    relevant = XPathField('@relevant')
    auto_launch = StringField("@auto_launch")
    redo_last = BooleanField("@redo_last")


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
    print_template = StringField('@print-template')

    title = NodeField('title/text', Text)
    lookup = NodeField('lookup', Lookup)
    fields = NodeListField('field', Field)
    actions = NodeListField('action', Action)
    details = NodeListField('detail', "self")
    _variables = NodeField('variables', DetailVariableList)
    relevant = StringField('@relevant')

    def _init_variables(self):
        if self._variables is None:
            self._variables = DetailVariableList()

    def _get_variables_node(self):
        self._init_variables()
        return self._variables.variables

    def _set_variables_node(self, value):
        self._init_variables()
        self._variables.variables = value

    variables = property(_get_variables_node, _set_variables_node)

    def has_variables(self):
        # can't check len(self.variables) directly since NodeList uses an
        # xpath to find its children which doesn't work here since
        # each node has a custom name
        return self._variables is not None and len(self.variables.node.getchildren()) > 0

    def get_variables(self):
        """
        :returns: List of DetailVariable objects
        """
        return [self.variables.mapper.to_python(node) for node in self.variables.node.getchildren()]

    def get_all_xpaths(self):
        result = set()

        if self.nodeset:
            result.add(self.nodeset)
        if self.has_variables():
            for variable in self.get_variables():
                result.add(variable.function)

        if self.actions:
            for action in self.actions:
                for frame in action.stack.frames:
                    result.add(frame.if_clause)
                    for datum in getattr(frame, 'datums', []):
                        result.add(datum.value)

        def _get_graph_config_xpaths(configuration):
            result = set()
            for config in configuration.configs:
                result.add(config.xpath_function)
            return result

        for field in self.fields:
            if field.template.form == 'graph':
                s = etree.tostring(field.template.node, encoding='utf-8')
                template = load_xmlobject_from_string(s, xmlclass=GraphTemplate)
                result.update(_get_graph_config_xpaths(template.graph.configuration))
                for series in template.graph.series:
                    result.add(series.nodeset)
                    result.update(_get_graph_config_xpaths(series.configuration))
            else:
                result.add(field.header.text.xpath_function)
                result.add(field.template.text.xpath_function)
                if field.template.text.xpath:
                    for variable in field.template.text.xpath.variables:
                        if variable.xpath:
                            result.add(str(variable.xpath.function))

        for detail in self.details:
            result.update(detail.get_all_xpaths())
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
    # releases_xform_resources = NodeListField('xform-update-info', ReleaseInfoXFormResource)
    locale_resources = NodeListField('locale', LocaleResource)
    media_resources = NodeListField('locale', MediaResource)
    practice_user_restore_resources = NodeListField('user-restore', PracticeUserRestoreResource)

    details = NodeListField('detail', Detail)
    entries = NodeListField('entry', Entry)
    menus = NodeListField('menu', Menu)
    endpoints = NodeListField('endpoint', SessionEndpoint)
    remote_requests = NodeListField('remote-request', RemoteRequest)

    fixtures = NodeListField('fixture', Fixture)
