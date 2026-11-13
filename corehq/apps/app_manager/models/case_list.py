import hashlib
import re

from couchdbkit.exceptions import BadValueError
from dimagi.ext.couchdbkit import (
    BooleanProperty,
    DictProperty,
    DocumentSchema,
    FloatProperty,
    IntegerProperty,
    SchemaListProperty,
    SchemaProperty,
    StringProperty,
)
from dimagi.utils.web import parse_int
from django.utils.translation import gettext as _

from corehq.apps.app_manager.const import (
    FORMATS_SUPPORTING_CASE_LIST_OPTIMIZATIONS,
)
from corehq.apps.app_manager.suite_xml.post_process.remote_requests import (
    RESULTS_INSTANCE,
)
from corehq.apps.app_manager.util import (
    module_loads_registry_case,
    module_uses_inline_search,
)
from corehq.apps.app_manager.xpath import dot_interpolate

from .base import (
    FormIdProperty,
    IndexedSchema,
    LabelProperty,
    rename_key,
)
from .mixins import NavMenuItemMediaMixin

FIELD_SEPARATOR = ':'


class MappingItem(DocumentSchema):
    key = StringProperty()
    # lang => localized string
    value = DictProperty()
    alt_text = LabelProperty()

    @property
    def treat_as_expression(self):
        """
        Returns if whether the key can be treated as a valid expression that can be included in
        condition-predicate of an if-clause for e.g. if(<expression>, value, ...)
        """
        special_chars = '{}()[]=<>."\'/'
        return any(special_char in self.key for special_char in special_chars)

    @property
    def key_as_variable(self):
        """
        Return an xml variable name to represent this key.

        If the key contains spaces or a condition-predicate of an if-clause,
        return a hash of the key with "h" prepended.
        If not, return the key with "k" prepended.

        The prepended characters prevent the variable name from starting with a
        numeral, which is illegal.
        """
        if re.search(r'\W', self.key) or self.treat_as_expression:
            return 'h{hash}'.format(hash=hashlib.md5(self.key.encode('UTF-8')).hexdigest()[:8])
        else:
            return 'k{key}'.format(key=self.key)

    def key_as_condition(self, property=None):
        if self.treat_as_expression:
            condition = dot_interpolate(self.key, property) if property else self.key
            return "{condition}".format(condition=condition)
        else:
            return "{property} = '{key}'".format(
                property=property,
                key=self.key
            )

    def ref_to_key_variable(self, index, sort_or_display):
        if sort_or_display == "sort":
            key_as_var = "{}, ".format(index)
        elif sort_or_display == "display":
            key_as_var = "${var_name}, ".format(var_name=self.key_as_variable)

        return key_as_var


class JRResourceProperty(StringProperty):

    def validate(self, value, required=True):
        super(JRResourceProperty, self).validate(value, required)
        if value is not None and not value.startswith('jr://'):
            raise BadValueError("JR Resources must start with 'jr://': {!r}".format(value))
        return value


class GraphAnnotations(IndexedSchema):
    display_text = DictProperty()
    x = StringProperty()
    y = StringProperty()


class GraphSeries(DocumentSchema):
    config = DictProperty()
    locale_specific_config = DictProperty()
    data_path = StringProperty(exclude_if_none=True)
    x_function = StringProperty(exclude_if_none=True)
    y_function = StringProperty(exclude_if_none=True)
    radius_function = StringProperty(exclude_if_none=True)


class GraphConfiguration(DocumentSchema):
    config = DictProperty()
    locale_specific_config = DictProperty()
    annotations = SchemaListProperty(GraphAnnotations)
    graph_type = StringProperty(exclude_if_none=True)
    series = SchemaListProperty(GraphSeries)


class DetailTab(IndexedSchema):
    """
    Represents a tab in the case detail screen on the phone.
    Each tab is itself a detail, nested inside the app's "main" detail.
    """
    header = DictProperty()

    # The first index, of all fields in the parent detail, that belongs to this tab
    starting_index = IntegerProperty()

    # A tab may be associated with a nodeset, resulting in a detail that
    # iterates through a set of entities rather than a single entity.
    # A nodeset is represented by one of the two properties:
    #   nodeset: An absolute xpath expression to iterate over
    #   nodeset_case_type: Iterate over all child cases of this type
    has_nodeset = BooleanProperty(default=False)
    nodeset = StringProperty(exclude_if_none=True)
    nodeset_case_type = StringProperty(exclude_if_none=True)
    nodeset_filter = StringProperty(exclude_if_none=True)   # only relevant if nodeset_case_type is populated

    # Display condition for the tab
    relevant = StringProperty(exclude_if_none=True)


class DetailColumn(IndexedSchema):
    """
    Represents a column in case selection screen on the phone. Ex:
        {
            'header': {'en': 'Sex', 'por': 'Sexo'},
            'model': 'case',
            'field': 'sex',
            'format': 'enum',
            'xpath': '.',
            'enum': [
                {'key': 'm', 'value': {'en': 'Male', 'por': 'Macho'},
                {'key': 'f', 'value': {'en': 'Female', 'por': 'Fêmea'},
            ],
        }

    """
    header = DictProperty()
    model = StringProperty(exclude_if_none=True)
    field = StringProperty()
    useXpathExpression = BooleanProperty(default=False)
    format = StringProperty(exclude_if_none=True)
    optimization = StringProperty(exclude_if_none=True)

    # Only applies to custom case list tile. grid_x and grid_y are zero-based values
    # representing the starting row and column.
    grid_x = IntegerProperty(required=False)
    grid_y = IntegerProperty(required=False)
    width = IntegerProperty(exclude_if_none=True)
    height = IntegerProperty(exclude_if_none=True)
    horizontal_align = StringProperty(exclude_if_none=True)
    vertical_align = StringProperty(exclude_if_none=True)
    font_size = StringProperty(exclude_if_none=True)
    show_border = BooleanProperty(exclude_if_none=True)
    show_shading = BooleanProperty(exclude_if_none=True)

    enum = SchemaListProperty(MappingItem)
    graph_configuration = SchemaProperty(GraphConfiguration)
    case_tile_field = StringProperty(exclude_if_none=True)

    late_flag = IntegerProperty(default=30)
    advanced = StringProperty(default="", exclude_if_none=True)
    filter_xpath = StringProperty(default="", exclude_if_none=True)
    time_ago_interval = FloatProperty(default=365.25)
    date_format = StringProperty(default="%d/%m/%y")
    endpoint_action_id = FormIdProperty(default="", exclude_if_none=True)

    @property
    def enum_dict(self):
        """for backwards compatibility with building 1.0 apps"""
        import warnings
        warnings.warn('You should not use enum_dict. Use enum instead',
                      DeprecationWarning)
        return dict((item.key, item.value) for item in self.enum)

    def rename_lang(self, old_lang, new_lang):
        for dct in [self.header] + [item.value for item in self.enum]:
            rename_key(dct, old_lang, new_lang)

    @property
    def field_type(self):
        if FIELD_SEPARATOR in self.field:
            return self.field.split(FIELD_SEPARATOR, 1)[0]
        else:
            return 'property'  # equivalent to property:parent/case_property

    @property
    def field_property(self):
        if FIELD_SEPARATOR in self.field:
            return self.field.split(FIELD_SEPARATOR, 1)[1]
        else:
            return self.field

    @classmethod
    def from_json(cls, data):
        from corehq.apps.app_manager.views.media_utils import (
            interpolate_media_path,
        )

        to_ret = cls.wrap(data)
        if to_ret.format == 'enum-image':
            # interpolate icons-paths
            for item in to_ret.enum:
                for lang, path in item.value.items():
                    item.value[lang] = interpolate_media_path(path)

        if to_ret.optimization and not to_ret.supports_optimizations:
            to_ret.optimization = None
        return to_ret

    @property
    def invisible(self):
        return self.format == 'invisible'

    @property
    def supports_optimizations(self):
        return self.useXpathExpression and self.format in FORMATS_SUPPORTING_CASE_LIST_OPTIMIZATIONS


class SortElement(IndexedSchema):
    """
    A sort entry for case list

    It should either have a field or a sort calculation to sort by.
    Having sort calculation makes field redundant.
    For legacy sort element entries that have both present, sort calculation is considered.
    """
    field = StringProperty()
    type = StringProperty()
    direction = StringProperty()
    blanks = StringProperty()
    display = DictProperty()
    sort_calculation = StringProperty(default="")

    def has_display_values(self):
        return any(s.strip() != '' for s in self.display.values())

    def valid(self):
        """
        returns if object is valid; along with an error message in case invalid
        """
        if not self.field and not self.sort_calculation:
            return False, _("Sort property needs a property or a calculation")
        return True, None


class CaseListLookupMixin(DocumentSchema):
    """
    Allows for the addition of Android Callouts to do lookups from the CaseList

        <lookup action="" image="" name="">
            <extra key="" value="" />
            <response key="" />
            <field>
                <header><text><locale id=""/></text></header>
                <template><text><xpath function=""/></text></template>
            </field>
        </lookup>

    """
    lookup_enabled = BooleanProperty(default=False)
    lookup_autolaunch = BooleanProperty(default=False)
    lookup_action = StringProperty(exclude_if_none=True)
    lookup_name = StringProperty(exclude_if_none=True)
    lookup_image = JRResourceProperty(required=False)

    lookup_extras = SchemaListProperty()
    lookup_responses = SchemaListProperty()

    lookup_display_results = BooleanProperty(default=False)  # Display callout results in case list?
    lookup_field_header = DictProperty()
    lookup_field_template = StringProperty(exclude_if_none=True)


class CaseTileGroupConfig(DocumentSchema):
    # e.g. "./index/parent"
    index_identifier = StringProperty()
    # number of rows of the tile to use for the group header
    header_rows = IntegerProperty(default=2)


class Detail(IndexedSchema, CaseListLookupMixin):
    """
    Full configuration for a case selection screen

    """
    display = StringProperty(choices=['short', 'long'])

    columns = SchemaListProperty(DetailColumn)
    get_columns = IndexedSchema.Getter('columns')

    tabs = SchemaListProperty(DetailTab)
    get_tabs = IndexedSchema.Getter('tabs')

    sort_elements = SchemaListProperty(SortElement)
    filter = StringProperty(exclude_if_none=True)

    instance_name = StringProperty(default='casedb')

    # If True, a small tile will display the case name after selection.
    persist_case_context = BooleanProperty()
    persistent_case_context_xml = StringProperty(default='case_name')

    # Custom variables to add into the <variables /> node
    custom_variables_dict = DictProperty(exclude_if_none=True)

    # Allow selection of mutiple cases. Only applies to 'short' details
    multi_select = BooleanProperty(default=False)

    # If True, enables auto selection of cases in a multi-select case list
    auto_select = BooleanProperty(default=False)

    # Sets a maximum selected value for manual and auto select multi-select case lists
    max_select_value = IntegerProperty(default=100)

    # If True, use case tiles in the case list
    case_tile_template = StringProperty(exclude_if_none=True)
    # If given, use this string for the case tile markup instead of the default temaplte
    custom_xml = StringProperty(exclude_if_none=True)

    persist_tile_on_forms = BooleanProperty()
    # use case tile context persisted over forms from another module
    persistent_case_tile_from_module = StringProperty(exclude_if_none=True)
    # If True, the in form tile can be pulled down to reveal all the case details.
    pull_down_tile = BooleanProperty()
    case_tile_group = SchemaProperty(CaseTileGroupConfig)

    #Only applies to 'short' details
    no_items_text = LabelProperty(default={'en': 'List is empty.'})

    select_text = LabelProperty(default={'en': 'Continue'})

    def get_instance_name(self, module):
        value_is_the_default = self.instance_name == 'casedb'
        if value_is_the_default:
            if module_uses_inline_search(module):
                return module.search_config.get_instance_name()
            elif module_loads_registry_case(module):
                return RESULTS_INSTANCE
        return self.instance_name

    def get_tab_spans(self):
        '''
        Return the starting and ending indices into self.columns deliminating
        the columns that should be in each tab.
        :return:
        '''
        tabs = list(self.get_tabs())
        ret = []
        for tab in tabs:
            try:
                end = tabs[tab.id + 1].starting_index
            except IndexError:
                end = len(self.columns)
            ret.append((tab.starting_index, end))
        return ret

    @parse_int([1])
    def get_column(self, i):
        return self.columns[i].with_id(i % len(self.columns), self)

    def rename_lang(self, old_lang, new_lang):
        for column in self.columns:
            column.rename_lang(old_lang, new_lang)

    def sort_nodeset_columns_for_long_detail(self):
        return (
            self.display == "long"
            and any(tab for tab in self.get_tabs() if tab.has_nodeset)
        )

    def has_persistent_tile(self):
        """
        Return True if configured to persist a case tile on forms
        """
        return self.persist_tile_on_forms and (self.case_tile_template or self.custom_xml)

    def overwrite_attrs(self, src_detail, attrs):
        """
        This method is used to overwrite a limited set of attributes
        based on a detail from another module and a list of attributes.

        This method is relevant only for short details.
        """
        case_tile_configuration_list = [
            'case_tile_template',
            'persist_tile_on_forms',
            'persistent_case_tile_from_module',
            'pull_down_tile',
            'persist_case_context',
            'persistent_case_context_xml',
            'case_tile_group',
        ]
        for attr in attrs:
            if attr == "case_tile_configuration":
                for ele in case_tile_configuration_list:
                    setattr(self, ele, getattr(src_detail, ele))
            else:
                setattr(self, attr, getattr(src_detail, attr))


class CaseList(IndexedSchema, NavMenuItemMediaMixin):

    label = LabelProperty()
    show = BooleanProperty(default=False)

    def rename_lang(self, old_lang, new_lang):
        rename_key(self.label, old_lang, new_lang)

    def get_app(self):
        return self._module.get_app()
