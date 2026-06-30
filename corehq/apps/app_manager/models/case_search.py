from dimagi.ext.couchdbkit import (
    BooleanProperty,
    DocumentSchema,
    IntegerProperty,
    SchemaListProperty,
    SchemaProperty,
    StringListProperty,
    StringProperty,
)

from corehq.apps.app_manager.suite_xml.post_process.remote_requests import (
    RESULTS_INSTANCE_BASE,
    RESULTS_INSTANCE_INLINE,
)
from corehq.apps.app_manager.xpath import (
    CaseClaimXpath,
)

from .base import (
    Assertion,
    LabelProperty,
)


class Itemset(DocumentSchema):
    instance_id = StringProperty(exclude_if_none=True)
    nodeset = StringProperty(exclude_if_none=True)
    label = StringProperty(exclude_if_none=True)
    value = StringProperty(exclude_if_none=True)
    sort = StringProperty(exclude_if_none=True)


class CaseSearchProperty(DocumentSchema):
    """
    Case properties available to search on.
    """
    name = StringProperty()
    label = LabelProperty()
    appearance = StringProperty(exclude_if_none=True)
    input_ = StringProperty(exclude_if_none=True)
    default_value = StringProperty(exclude_if_none=True)
    hint = LabelProperty()
    hidden = BooleanProperty(default=False)
    allow_blank_value = BooleanProperty(default=False)
    exclude = BooleanProperty(default=False)
    required = SchemaProperty(Assertion)
    validations = SchemaListProperty(Assertion)

    # applicable when appearance is a receiver
    receiver_expression = StringProperty(exclude_if_none=True)
    itemset = SchemaProperty(Itemset)

    is_group = BooleanProperty(default=False)
    group_key = StringProperty(exclude_if_none=True)


class DefaultCaseSearchProperty(DocumentSchema):
    """Case Properties with fixed value to search on"""
    property = StringProperty()
    defaultValue = StringProperty(exclude_if_none=True)


class CaseSearchCustomSortProperty(DocumentSchema):
    """Sort properties to be applied to search before results are filtered"""
    property_name = StringProperty()
    sort_type = StringProperty()
    direction = StringProperty()


class CaseSearch(DocumentSchema):
    """
    Properties and search command label

    Removed fields (do not reuse):
    - again_label: Removed with SSCS migration (Feb 2026)
    - search_again_label: Removed with SSCS migration (Feb 2026)
    - dynamic_search: Removed deprecated functionality (Apr 2026)
    - command_label: Superseded by search_label (2021 migration)
    - search_label: Removed; search button always uses default label (Apr 2026)
    - additional_relevant: Removing that feature (Apr 2026)
    - search_filter: Removed with USH_SEARCH_FILTER toggle (Apr 2026)
      These fields may still exist in CouchDB documents but are no longer used.
    """
    case_search_endpoint_id = IntegerProperty(exclude_if_none=True)
    search_button_label = LabelProperty(default={'en': 'Search All Cases'})
    properties = SchemaListProperty(CaseSearchProperty)
    auto_launch = BooleanProperty(default=False)        # if true, skip the casedb case list
    default_search = BooleanProperty(default=False)     # if true, skip the search fields screen
    search_button_display_condition = StringProperty(exclude_if_none=True)
    default_properties = SchemaListProperty(DefaultCaseSearchProperty)
    custom_sort_properties = SchemaListProperty(CaseSearchCustomSortProperty)
    blacklisted_owner_ids_expression = StringProperty(exclude_if_none=True)
    additional_case_types = StringListProperty()
    data_registry = StringProperty(exclude_if_none=True)
    data_registry_workflow = StringProperty(exclude_if_none=True)  # one of REGISTRY_WORKFLOW_*
    additional_registry_cases = StringListProperty()               # list of xpath expressions
    title_label = LabelProperty(default={})
    description = LabelProperty(default={})
    include_all_related_cases = BooleanProperty(default=False)
    search_on_clear = BooleanProperty(default=False)

    # case property referencing another case's ID
    custom_related_case_property = StringProperty(exclude_if_none=True)

    inline_search = BooleanProperty(default=False)
    instance_name = StringProperty(exclude_if_none=True)  # only applicable to inline_search

    @property
    def case_session_var(self):
        return "search_case_id"

    def get_instance_name(self):
        if self.instance_name:
            return f'{RESULTS_INSTANCE_BASE}{self.instance_name}'
        else:
            return RESULTS_INSTANCE_INLINE

    def get_relevant(self, case_session_var, multi_select=False):
        xpath = CaseClaimXpath(case_session_var)
        default_condition = xpath.multi_case_relevant() if multi_select else xpath.default_relevant()
        return default_condition

    def get_search_title_label(self, app, lang, for_default=False):
        if for_default:
            lang = app.default_language
        # Some apps have undefined labels incorrectly set to None, normalize here
        return self.title_label.get(lang) or ''

    def overwrite_attrs(self, src_config, slugs):
        if 'search_properties' in slugs:
            self.properties = src_config.properties
        if 'search_default_properties' in slugs:
            self.default_properties = src_config.default_properties
        if 'search_claim_options' in slugs:
            # all options other than 'properties' and 'default_properties'
            attrs = self.keys() - self.dynamic_properties().keys() - {'properties', 'default_properties'}
            for attr in attrs:
                setattr(self, attr, getattr(src_config, attr))
