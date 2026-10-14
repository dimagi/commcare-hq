import itertools
from collections import Counter

from dimagi.ext.couchdbkit import (
    BooleanProperty,
    DictProperty,
    DocumentSchema,
    ListProperty,
    SchemaDictProperty,
    SchemaListProperty,
    SchemaProperty,
    StringProperty,
)
from memoized import memoized

from corehq.apps.app_manager import const

from .base import IndexedSchema


class FormActionCondition(DocumentSchema):
    """
    The condition under which to open/update/close a case/referral

    Either {'type': 'if', 'question': '/xpath/to/node', 'answer': 'value'}
    in which case the action takes place if question has answer answer,
    or {'type': 'always'} in which case the action always takes place.
    """
    type = StringProperty(choices=["if", "always", "never"], default="never")
    question = StringProperty()
    answer = StringProperty()
    operator = StringProperty(choices=['=', 'selected', 'boolean_true'], default='=')

    def is_active(self):
        return self.type in ('if', 'always')


class FormAction(DocumentSchema):
    """
    Corresponds to Case XML

    """
    condition = SchemaProperty(FormActionCondition)

    def is_active(self):
        return self.condition.is_active()

    @classmethod
    def get_action_paths(cls, action):
        if action.condition.type == 'if':
            yield action.condition.question

        for __, path in cls.get_action_properties(action):
            yield path

    @classmethod
    def get_action_properties(cls, action):
        action_properties = action.properties()
        if 'name_path' in action_properties and action.name_path:
            yield 'name', action.name_path
        if action_properties.get('name_update') and action.name_update and action.name_update.question_path:
            yield 'name', action.name_update.question_path
        if 'external_id' in action_properties and action.external_id:
            yield 'external_id', action.external_id
        if 'update' in action_properties and action.update:
            for name, conditional_case_update in action.update.items():
                yield name, conditional_case_update.question_path
        if 'case_properties' in action_properties:
            for name, conditional_case_update in action.case_properties.items():
                yield name, conditional_case_update.question_path
        if 'preload' in action_properties:
            for path, name in action.preload.items():
                yield name, path


class ConditionalCaseUpdate(DocumentSchema):
    question_path = StringProperty()
    update_mode = StringProperty(
        choices=[const.UPDATE_MODE_ALWAYS, const.UPDATE_MODE_EDIT],
        default=const.UPDATE_MODE_ALWAYS
    )


class UpdateCaseAction(FormAction):
    update = SchemaDictProperty(ConditionalCaseUpdate)
    conflicts = SchemaDictProperty(SchemaListProperty(ConditionalCaseUpdate))


class PreloadAction(FormAction):

    preload = DictProperty()

    def is_active(self):
        return bool(self.preload)


class UpdateReferralAction(FormAction):

    followup_date = StringProperty()

    def get_followup_date(self):
        if self.followup_date:
            return "if(date({followup_date}) >= date(today()), {followup_date}, date(today() + 2))".format(
                followup_date=self.followup_date,
            )
        return self.followup_date or "date(today() + 2)"


class OpenReferralAction(UpdateReferralAction):

    name_path = StringProperty()


class OpenCaseAction(FormAction):

    name_update = SchemaProperty(ConditionalCaseUpdate)
    conflicts = SchemaListProperty(ConditionalCaseUpdate)
    external_id = StringProperty()


class OpenSubCaseAction(FormAction, IndexedSchema):

    case_type = StringProperty()
    name_update = SchemaProperty(ConditionalCaseUpdate)
    reference_id = StringProperty()
    case_properties = SchemaDictProperty(ConditionalCaseUpdate)
    repeat_context = StringProperty()
    # relationship = "child" for index to a parent case (default)
    # relationship = "extension" for index to a host case
    relationship = StringProperty(choices=['child', 'extension'], default='child')

    close_condition = SchemaProperty(FormActionCondition)

    @property
    def form_element_name(self):
        return 'subcase_{}'.format(self.id)


class FormActions(DocumentSchema):
    open_case = SchemaProperty(OpenCaseAction)
    update_case = SchemaProperty(UpdateCaseAction)
    close_case = SchemaProperty(FormAction)
    open_referral = SchemaProperty(OpenReferralAction)
    update_referral = SchemaProperty(UpdateReferralAction)
    close_referral = SchemaProperty(FormAction)

    case_preload = SchemaProperty(PreloadAction)
    referral_preload = SchemaProperty(PreloadAction)
    load_from_form = SchemaProperty(PreloadAction)  # DEPRECATED

    usercase_update = SchemaProperty(UpdateCaseAction)
    usercase_preload = SchemaProperty(PreloadAction)

    subcases = SchemaListProperty(OpenSubCaseAction)

    get_subcases = IndexedSchema.Getter('subcases')

    def all_property_names(self):
        names = set()
        names.update(self.update_case.update.keys())
        names.update(list(self.case_preload.preload.values()))
        for subcase in self.subcases:
            names.update(list(subcase.case_properties.keys()))
        names.update(list(self.usercase_update.update.keys()))
        names.update(list(self.usercase_preload.preload.values()))
        return names

    def count_subcases_per_repeat_context(self):
        return Counter([action.repeat_context for action in self.subcases])


class CaseIndex(DocumentSchema):
    tag = StringProperty()
    reference_id = StringProperty(default='parent')
    relationship = StringProperty(choices=['child', 'extension', 'question'], default='child')
    # if relationship is 'question', this is the question path
    # question's response must be either "child" or "extension"
    relationship_question = StringProperty(default='')


class AdvancedAction(IndexedSchema):
    case_type = StringProperty()
    case_tag = StringProperty()

    case_properties = SchemaDictProperty(ConditionalCaseUpdate)

    # case_indices = NotImplemented

    close_condition = SchemaProperty(FormActionCondition)

    __eq__ = DocumentSchema.__eq__

    def get_paths(self):
        for smart_case_update in self.case_properties.values():
            yield smart_case_update.question_path

        if self.close_condition.type == 'if':
            yield self.close_condition.question

    def get_property_names(self):
        return set(self.case_properties.keys())

    @property
    def is_subcase(self):
        return bool(self.case_indices)

    @property
    def form_element_name(self):
        return "case_{}".format(self.case_tag)


class AutoSelectCase(DocumentSchema):
    """
    Configuration for auto-selecting a case.
    Attributes:
        value_source    Reference to the source of the value. For mode = fixture,
                        this represents the LookupTable ID. For mode = case
                        this represents the 'case_tag' for the case.
                        The modes 'user' and 'raw' don't require a value_source.
        value_key       The actual field that contains the case ID. Can be a case
                        index or a user data key or a fixture field name or the raw
                        xpath expression.

    """
    mode = StringProperty(choices=[const.AUTO_SELECT_USER,
                                   const.AUTO_SELECT_FIXTURE,
                                   const.AUTO_SELECT_CASE,
                                   const.AUTO_SELECT_USERCASE,
                                   const.AUTO_SELECT_RAW])
    value_source = StringProperty()
    value_key = StringProperty(required=True)


class LoadCaseFromFixture(DocumentSchema):
    """
    fixture_nodeset:     nodeset that returns the fixture options to display
    fixture_tag:         id of session datum where the result of user selection will be stored
    fixture_variable:    value from the fixture to store from the selection
    auto_select_fixture: boolean to autoselect the value if the nodeset only returns 1 result
    case_property:       case property to filter on
    arbitrary_datum_*:   adds an arbitrary datum with function before the action
    """
    fixture_nodeset = StringProperty()
    fixture_tag = StringProperty()
    fixture_variable = StringProperty()
    auto_select_fixture = BooleanProperty(default=False)
    case_property = StringProperty(default='')
    auto_select = BooleanProperty(default=False)
    arbitrary_datum_id = StringProperty()
    arbitrary_datum_function = StringProperty()


class LoadUpdateAction(AdvancedAction):
    """
    details_module:           Use the case list configuration from this module to show the cases.
    preload:                  Value from the case to load into the form. Keys are question paths,
                              values are case properties.
    auto_select:              Configuration for auto-selecting the case
    load_case_from_fixture:   Configuration for loading a case using fixture data
    show_product_stock:       If True list the product stock using the module's Product List
                              configuration.
    product_program:          Only show products for this CommCare Supply program.
    case_index:               Used when a case should be created/updated as a child or extension case
                              of another case.
    """
    details_module = StringProperty()
    preload = DictProperty()
    auto_select = SchemaProperty(AutoSelectCase, default=None)
    load_case_from_fixture = SchemaProperty(LoadCaseFromFixture, default=None)
    show_product_stock = BooleanProperty(default=False)
    product_program = StringProperty()
    case_index = SchemaProperty(CaseIndex)

    @property
    def case_indices(self):
        # Allows us to ducktype AdvancedOpenCaseAction
        return [self.case_index] if self.case_index.tag else []

    @case_indices.setter
    def case_indices(self, value):
        if len(value) > 1:
            raise ValueError('A LoadUpdateAction cannot have more than one case index')
        if value:
            self.case_index = value[0]
        else:
            self.case_index = CaseIndex()

    @case_indices.deleter
    def case_indices(self):
        self.case_index = CaseIndex()

    def get_paths(self):
        for path in super(LoadUpdateAction, self).get_paths():
            yield path

        for path in self.preload.keys():
            yield path

    def get_property_names(self):
        names = super(LoadUpdateAction, self).get_property_names()
        names.update(list(self.preload.values()))
        return names

    @property
    def case_session_var(self):
        return 'case_id_{0}'.format(self.case_tag)


class AdvancedOpenCaseAction(AdvancedAction):
    name_update = SchemaProperty(ConditionalCaseUpdate)
    repeat_context = StringProperty()
    case_indices = SchemaListProperty(CaseIndex)

    open_condition = SchemaProperty(FormActionCondition)

    def get_paths(self):
        for path in super(AdvancedOpenCaseAction, self).get_paths():
            yield path

        yield self.name_update.question_path

        if self.open_condition.type == 'if':
            yield self.open_condition.question

    @property
    def case_session_var(self):
        return 'case_id_new_{}_{}'.format(self.case_type, self.id)


class ArbitraryDatum(DocumentSchema):
    datum_id = StringProperty(default=None)
    datum_function = StringProperty(default=None)


class AdvancedFormActions(DocumentSchema):
    load_update_cases = SchemaListProperty(LoadUpdateAction)

    open_cases = SchemaListProperty(AdvancedOpenCaseAction)

    get_load_update_actions = IndexedSchema.Getter('load_update_cases')
    get_open_actions = IndexedSchema.Getter('open_cases')

    def get_all_actions(self):
        return itertools.chain(self.get_load_update_actions(), self.get_open_actions())

    def get_subcase_actions(self):
        return (a for a in self.get_all_actions() if a.case_indices)

    def get_open_subcase_actions(self, parent_case_type=None):
        for action in self.open_cases:
            if action.case_indices:
                if not parent_case_type:
                    yield action
                else:
                    if any(self.actions_meta_by_tag[case_index.tag]['action'].case_type == parent_case_type
                           for case_index in action.case_indices):
                        yield action

    def get_case_tags(self):
        for action in self.get_all_actions():
            yield action.case_tag

    def get_action_from_tag(self, tag):
        return self.actions_meta_by_tag.get(tag, {}).get('action', None)

    @property
    def actions_meta_by_tag(self):
        return self._action_meta()['by_tag']

    @property
    def actions_meta_by_parent_tag(self):
        return self._action_meta()['by_parent_tag']

    @property
    def auto_select_actions(self):
        return self._action_meta()['by_auto_select_mode']

    @memoized
    def _action_meta(self):
        meta = {
            'by_tag': {},
            'by_parent_tag': {},
            'by_auto_select_mode': {
                const.AUTO_SELECT_USER: [],
                const.AUTO_SELECT_CASE: [],
                const.AUTO_SELECT_FIXTURE: [],
                const.AUTO_SELECT_USERCASE: [],
                const.AUTO_SELECT_RAW: [],
            }
        }

        def add_actions(type, action_list):
            for action in action_list:
                meta['by_tag'][action.case_tag] = {
                    'type': type,
                    'action': action
                }
                for parent in action.case_indices:
                    meta['by_parent_tag'][parent.tag] = {
                        'type': type,
                        'action': action
                    }
                if type == 'load' and action.auto_select and action.auto_select.mode:
                    meta['by_auto_select_mode'][action.auto_select.mode].append(action)

        add_actions('load', self.get_load_update_actions())
        add_actions('open', self.get_open_actions())

        return meta

    def count_subcases_per_repeat_context(self):
        return Counter([action.repeat_context for action in self.get_open_subcase_actions()])


class CaseLoadReference(DocumentSchema):
    """
    This is the schema for a load reference that is used in validation and expected
    to be worked with when using `CaseReferences`. The format is different from the
    dict of:

    {
      'path': ['list', 'of', 'properties']
    }

    That is stored on the model and expected in Vellum, but as we add more information
    (like case types) to the load model this format will be easier to extend.
    """
    _allow_dynamic_properties = False
    path = StringProperty()
    properties = ListProperty(str)


class CaseSaveReference(DocumentSchema):
    """
    This is the schema for what Vellum writes to HQ and what is expected to be stored on the
    model (reference by a dict where the keys are paths).
    """
    _allow_dynamic_properties = False
    case_type = StringProperty()
    properties = ListProperty(str)
    create = BooleanProperty(default=False)
    close = BooleanProperty(default=False)


class CaseSaveReferenceWithPath(CaseSaveReference):
    """
    Like CaseLoadReference, this is the model that is expected to be worked with as it
    contains the complete information about the reference in a single place.
    """
    path = StringProperty()


class CaseReferences(DocumentSchema):
    """
    The case references associated with a form. This is dependent on Vellum's API that sends
    case references to HQ.

    load: is a dict of question paths to lists of properties (see `CaseLoadReference`),
    save: is a dict of question paths to `CaseSaveReference` objects.

    The intention is that all usage of the objects goes through the `get_load_references` and
    `get_save_references` helper functions.
    """
    _allow_dynamic_properties = False
    load = DictProperty()
    save = SchemaDictProperty(CaseSaveReference)

    def validate(self, required=True):
        super(CaseReferences, self).validate()
        # call this method to force validation to run on the other referenced types
        # since load is not a defined schema (yet)
        list(self.get_load_references())

    def get_load_references(self):
        """
        Returns a generator of `CaseLoadReference` objects containing all the load references.
        """
        for path, properties in self.load.items():
            yield CaseLoadReference(path=path, properties=list(properties))

    def get_save_references(self):
        """
        Returns a generator of `CaseSaveReferenceWithPath` objects containing all the save references.
        """
        for path, reference in self.save.items():
            ref_copy = reference.to_json()
            ref_copy['path'] = path
            yield CaseSaveReferenceWithPath.wrap(ref_copy)
