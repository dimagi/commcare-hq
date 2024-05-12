"""
RemoteRequestsHelper
--------------------

The ``<remote-request>`` descends from the ``<entry>``.
Remote requests provide support for CommCare to request data from the server
and then allow the user to select an item from that data and use it as a datum for a form.
In practice, remote requests are only used for case search and claim workflows.

This case search config UI in app manager is a thin wrapper around the various elements that are part of
``<remote-request>``, which means ``RemoteRequestsHelper`` is not especially complicated, although it is rather
long.

Case search and claim is typically an optional part of a workflow.
In this use case, the remote request is accessed via an action, and the
`rewind <https://github.com/dimagi/commcare-core/wiki/SessionStack#mark-and-rewind>`_ construct
is used to go back to the main flow.
However, the flag ``USH_INLINE_SEARCH`` supports remote requests being made in the main flow of a session. When
using this flag, a ``<post>`` and query datums are added to a normal form ``<entry>``. This makes search inputs
available after the search, rather than having them destroyed by rewinding.

This module includes ``SessionEndpointRemoteRequestFactory``, which generates remote requests for use by session
endpoints. This functionality exists for the sake of smart links: whenever a user clicks a smart link,
any cases that are part of the smart link need to be claimed so the user can access them.
"""
from django.utils.functional import cached_property

from corehq import toggles
from corehq.apps.app_manager import id_strings
from corehq.apps.app_manager.suite_xml.contributors import (
    PostProcessor,
)
from corehq.apps.app_manager.suite_xml.post_process.endpoints import EndpointsHelper
from corehq.apps.app_manager.suite_xml.post_process.workflow import WorkflowDatumMeta
from corehq.apps.app_manager.suite_xml.sections.details import DetailsHelper
from corehq.apps.app_manager.suite_xml.utils import get_ordered_case_types_for_module
from corehq.apps.app_manager.suite_xml.xml_models import (
    CalculatedPropertyXPath,
    Command,
    Display,
    Hint,
    InstanceDatum,
    Itemset,
    PushFrame,
    QueryData,
    QueryPrompt,
    QueryPromptGroup,
    RemoteRequest,
    RemoteRequestPost,
    RemoteRequestQuery,
    RemoteRequestSession,
    Required,
    SessionDatum,
    Stack,
    StackJump,
    Text,
    TextXPath,
    Validation,
    XPathVariable,
)
from corehq.apps.app_manager.util import (
    is_linked_app,
    module_offers_search,
    module_uses_smart_links,
    module_offers_registry_search,
    module_uses_inline_search,
    module_uses_include_all_related_cases,
    module_uses_inline_search_with_parent_relationship_parent_select,
)
from corehq.apps.app_manager.xpath import (
    CaseClaimXpath,
    CaseIDXPath,
    SearchSelectedCasesInstanceXpath,
    CaseTypeXpath,
    InstanceXpath,
    interpolate_xpath,
    session_var,
    XPath,
)
from corehq.apps.case_search.const import COMMCARE_PROJECT, EXCLUDE_RELATED_CASES_FILTER
from corehq.apps.case_search.models import (
    CASE_SEARCH_BLACKLISTED_OWNER_ID_KEY,
    CASE_SEARCH_CUSTOM_RELATED_CASE_PROPERTY_KEY,
    CASE_SEARCH_REGISTRY_ID_KEY,
    CASE_SEARCH_INCLUDE_ALL_RELATED_CASES_KEY,
    CASE_SEARCH_SORT_KEY,
    CASE_SEARCH_XPATH_QUERY_KEY,
)
from corehq.util.timer import time_method
from corehq.util.view_utils import absolute_reverse

# The name of the instance where search results are stored
RESULTS_INSTANCE = 'results'
RESULTS_INSTANCE_BASE = f'{RESULTS_INSTANCE}:'
RESULTS_INSTANCE_INLINE = 'results:inline'

# The name of the instance where search results are stored when querying a data registry
REGISTRY_INSTANCE = 'registry'

SESSION_INSTANCE = 'commcaresession'


class QuerySessionXPath(InstanceXpath):
    id = SESSION_INSTANCE

    @property
    def path(self):
        return 'session/data/{}'.format(self)


class RemoteRequestFactory(object):
    def __init__(self, suite, module, detail_section_elements,
                 case_session_var=None, storage_instance=RESULTS_INSTANCE, exclude_relevant=False):
        self.suite = suite
        self.app = module.get_app()
        self.domain = self.app.domain
        self.module = module
        self.detail_section_elements = detail_section_elements
        self.storage_instance = storage_instance
        self.exclude_relevant = exclude_relevant
        if case_session_var:
            self.case_session_var = case_session_var
        else:
            if self.module.is_multi_select():
                # the instance is dynamic and its ID matches the datum ID
                self.case_session_var = SearchSelectedCasesInstanceXpath.default_id
            else:
                self.case_session_var = self.module.search_config.case_session_var

    def build_remote_request(self):
        return RemoteRequest(
            post=self.build_remote_request_post(),
            command=self.build_command(),
            session=self.build_session(),
            stack=self.build_stack(),
        )

    def build_remote_request_post(self):
        kwargs = {
            "url": absolute_reverse('claim_case', args=[self.domain]),
            "data": [
                self.build_case_id_query_data(),
            ],
        }
        relevant = self.get_post_relevant()
        if relevant:
            kwargs["relevant"] = relevant
        return RemoteRequestPost(**kwargs)

    def build_case_id_query_data(self):
        data = QueryData(key='case_id')
        if self.module.is_multi_select():
            data.ref = "."
            data.nodeset = self._get_multi_select_nodeset()
            if not self.exclude_relevant:
                data.exclude = self._get_multi_select_exclude()
        else:
            data.ref = QuerySessionXPath(self.case_session_var).instance()
            if (not self.exclude_relevant
            and module_uses_inline_search_with_parent_relationship_parent_select(self.module)):
                data.exclude = CaseIDXPath(data.ref).case().count().neq(0)
        return data

    def _get_multi_select_nodeset(self):
        return SearchSelectedCasesInstanceXpath(self.case_session_var).instance()

    def _get_multi_select_exclude(self):
        return CaseIDXPath(XPath("current()").slash(".")).case().count().eq(1)

    def get_post_relevant(self):
        if self.exclude_relevant:
            return None
        case_not_claimed = self.module.search_config.get_relevant(
            self.case_session_var, self.module.is_multi_select())
        if module_uses_smart_links(self.module):
            case_in_project = self._get_smart_link_rewind_xpath()
            return XPath.and_(case_not_claimed, case_in_project)
        else:
            return case_not_claimed

    def build_command(self):
        return Command(
            id=id_strings.search_command(self.module),
            display=Display(
                text=Text(locale_id=id_strings.case_search_locale(self.module)),
            ),
        )

    def build_title(self):
        return Display(
            text=Text(locale_id=id_strings.case_search_title_translation(self.module))
        )

    def build_description(self):
        return Display(
            text=Text(locale_id=id_strings.case_search_description_locale(self.module))
        )

    @cached_property
    def _details_helper(self):
        return DetailsHelper(self.app)

    def build_session(self):
        return RemoteRequestSession(
            queries=self.build_remote_request_queries(),
            data=self.build_remote_request_datums(),
        )

    def build_remote_request_queries(self):
        kwargs = {
            "url": absolute_reverse('app_aware_remote_search', args=[self.app.domain, self.app._id]),
            "storage_instance": self.storage_instance,
            "template": 'case',
            "title": self.build_title() if self.app.enable_case_search_title_translation else None,
            "description": self.build_description() if self.module.search_config.description != {} else None,
            "data": self._remote_request_query_datums,
            "prompts": self.build_query_prompts(),
            "prompt_groups": self.build_query_prompt_groups(),
            "default_search": self.module.search_config.default_search,
            "dynamic_search": self.app.split_screen_dynamic_search and not self.module.is_auto_select()
        }
        if self.module.search_config.search_on_clear and toggles.SPLIT_SCREEN_CASE_SEARCH.enabled(self.app.domain):
            kwargs["search_on_clear"] = (self.module.search_config.search_on_clear
                and not self.module.is_auto_select())
        return [
            RemoteRequestQuery(**kwargs)
        ]

    def build_remote_request_datums(self):
        if self.module.case_details.short.custom_xml:
            short_detail_id = 'case_short'
            long_detail_id = 'case_long'
        else:
            short_detail_id = 'search_short'
            long_detail_id = 'search_long'

        nodeset = CaseTypeXpath(self.module.case_type).case(instance_name=self.storage_instance)
        if toggles.USH_CASE_CLAIM_UPDATES.enabled(self.app.domain):
            additional_types = list(set(self.module.additional_case_types) - {self.module.case_type})
            if additional_types:
                nodeset = CaseTypeXpath(self.module.case_type).cases(
                    additional_types, instance_name=self.storage_instance)
            if self.module.search_config.search_filter and toggles.USH_SEARCH_FILTER.enabled(self.app.domain):
                nodeset = f"{nodeset}[{interpolate_xpath(self.module.search_config.search_filter)}]"
        nodeset += EXCLUDE_RELATED_CASES_FILTER

        datum_cls = InstanceDatum if self.module.is_multi_select() else SessionDatum
        return [datum_cls(
            id=self.case_session_var,
            nodeset=nodeset,
            value='./@case_id',
            detail_select=self._details_helper.get_detail_id_safe(self.module, short_detail_id),
            detail_confirm=self._details_helper.get_detail_id_safe(self.module, long_detail_id),
            autoselect=self.module.is_auto_select(),
            max_select_value=self.module.max_select_value,
        )]

    @cached_property
    def _remote_request_query_datums(self):
        datums = [
            QueryData(key='case_type', ref=f"'{case_type}'")
            for case_type in get_ordered_case_types_for_module(self.module)
        ]

        datums.extend(
            QueryData(key=c.property, ref=c.defaultValue)
            for c in self.module.search_config.default_properties
        )
        if self.module.search_config.blacklisted_owner_ids_expression:
            datums.append(
                QueryData(
                    key=CASE_SEARCH_BLACKLISTED_OWNER_ID_KEY,
                    ref=self.module.search_config.blacklisted_owner_ids_expression,
                )
            )
        if module_offers_registry_search(self.module):
            datums.append(
                QueryData(
                    key=CASE_SEARCH_REGISTRY_ID_KEY,
                    ref=f"'{self.module.search_config.data_registry}'",
                )
            )
        if self.module.search_config.custom_related_case_property:
            datums.append(
                QueryData(
                    key=CASE_SEARCH_CUSTOM_RELATED_CASE_PROPERTY_KEY,
                    ref=f"'{self.module.search_config.custom_related_case_property}'",
                )
            )
        if (module_uses_include_all_related_cases(self.module)):
            datums.append(
                QueryData(
                    key=CASE_SEARCH_INCLUDE_ALL_RELATED_CASES_KEY,
                    ref="'true'",
                )
            )
        if self.module.search_config.custom_sort_properties:
            refs = []
            for sort_property in self.module.search_config.custom_sort_properties:
                direction = '-' if sort_property.direction == 'descending' else '+'
                sort_type = sort_property.sort_type or 'exact'
                refs.append(f"{direction}{sort_property.property_name}:{sort_type}")
            datums.append(
                QueryData(
                    key=CASE_SEARCH_SORT_KEY,
                    ref=f"'{','.join(refs)}'",
                )
            )
        if module_uses_inline_search_with_parent_relationship_parent_select(self.module):
            parent_module_id = self.module.parent_select.module_id
            parent_module = self.app.get_module_by_unique_id(parent_module_id)
            parent_case_type = parent_module.case_type
            datums.append(
                QueryData(
                    key=CASE_SEARCH_XPATH_QUERY_KEY,
                    ref=f"\"ancestor-exists(parent, @case_type='{parent_case_type}')\""
                )
            )

        return datums

    def build_query_prompts(self):
        prompts = []
        prompt_properties = [prop for prop in self.module.search_config.properties if not prop.is_group]
        for prop in prompt_properties:
            text = Text(locale_id=id_strings.search_property_locale(self.module, prop.name))

            if prop.hint:
                display = Display(
                    text=text,
                    hint=Hint(text=Text(locale_id=id_strings.search_property_hint_locale(self.module, prop.name)))
                )
            else:
                display = Display(text=text)

            kwargs = {
                'key': prop.name,
                'display': display
            }
            if not prop.appearance or prop.itemset.nodeset:
                kwargs['receive'] = prop.receiver_expression
            if prop.hidden:
                kwargs['hidden'] = prop.hidden
            if prop.appearance and self.app.enable_search_prompt_appearance:
                if prop.appearance == 'address':
                    kwargs['input_'] = prop.appearance
                else:
                    kwargs['appearance'] = prop.appearance
            if prop.input_:
                kwargs['input_'] = prop.input_
            if prop.default_value and self.app.enable_default_value_expression:
                kwargs['default_value'] = prop.default_value
            if prop.itemset.nodeset:
                kwargs['itemset'] = Itemset(
                    nodeset=prop.itemset.nodeset,
                    label_ref=prop.itemset.label,
                    value_ref=prop.itemset.value,
                    sort_ref=prop.itemset.sort,
                )
            if prop.allow_blank_value:
                kwargs['allow_blank_value'] = prop.allow_blank_value
            if prop.exclude:
                kwargs['exclude'] = "true()"
            if prop.required.test:
                kwargs['required'] = Required(
                    test=interpolate_xpath(prop.required.test),
                    text=[Text(locale_id=id_strings.search_property_required_text(self.module, prop.name))],
                )
            if prop.validations:
                kwargs['validations'] = [
                    Validation(
                        # don't interpolate dots since "." is a valid reference here
                        test=interpolate_xpath(validation.test, interpolate_dots=False),
                        text=[Text(
                            locale_id=id_strings.search_property_validation_text(self.module, prop.name, i)
                        )] if validation.has_text else [],
                    )
                    for i, validation in enumerate(prop.validations)
                ]
            if prop.group_key:
                kwargs['group_key'] = prop.group_key
            prompts.append(QueryPrompt(**kwargs))
        return prompts

    def build_query_prompt_groups(self):
        prompts = []
        prompt_group_properties = [prop for prop in self.module.search_config.properties if prop.is_group]
        for prop in prompt_group_properties:
            text = Text(locale_id=id_strings.search_property_locale(self.module, prop.group_key))
            prompts.append(QueryPromptGroup(**{
                'key': prop.group_key,
                'display': Display(text=text)
            }))
        return prompts

    def build_stack(self):
        stack = Stack()
        rewind_if = None
        if module_uses_smart_links(self.module):
            rewind_if = self._get_smart_link_rewind_xpath()
            # For case in another domain, jump to that other domain
            frame = PushFrame(if_clause=XPath.not_(rewind_if))
            frame.add_datum(StackJump(
                url=Text(
                    xpath=TextXPath(
                        function=self.get_smart_link_function(),
                        variables=self.get_smart_link_variables(),
                    ),
                ),
            ))
            stack.add_frame(frame)
        frame = PushFrame(if_clause=rewind_if)
        frame.add_rewind(QuerySessionXPath(self.case_session_var).instance())
        stack.add_frame(frame)
        return stack

    def _get_smart_link_rewind_xpath(self):
        user_domain_xpath = session_var(COMMCARE_PROJECT, path="user/data")
        # For case in same domain, do a regular case claim rewind
        return self._get_case_domain_xpath().eq(user_domain_xpath)

    def get_smart_link_function(self):
        # Returns XPath that will evaluate to a URL.
        # For example, return value could be
        #   concat('https://www.cchq.org/a/', $domain, '/app/v1/123/smartlink/', '?arg1=', $arg1, '&arg2=', $arg2)
        # Which could evaluate to
        #   https://www.cchq.org/a/mydomain/app/v1/123/smartlink/?arg1=abd&arg2=def
        app_id = self.app.upstream_app_id if is_linked_app(self.app) else self.app.origin_id
        url = absolute_reverse("session_endpoint", args=["---", app_id, self.module.session_endpoint_id])
        prefix, suffix = url.split("---")
        params = ""
        argument_ids = self.endpoint_argument_ids
        if argument_ids:
            params = f", '?{argument_ids[-1]}=', ${argument_ids[-1]}"
            for argument_id in argument_ids[:-1]:
                params += f", '&{argument_id}=', ${argument_id}"
        return f"concat('{prefix}', $domain, '{suffix}'{params})"

    def get_smart_link_variables(self):
        variables = [
            XPathVariable(
                name="domain",
                xpath=CalculatedPropertyXPath(function=self._get_case_domain_xpath()),
            ),
        ]
        argument_ids = self.endpoint_argument_ids
        if argument_ids:
            for argument_id in argument_ids[:-1]:
                variables.append(XPathVariable(
                    name=argument_id,
                    xpath=CalculatedPropertyXPath(function=QuerySessionXPath(argument_id).instance()),
                ))
            # Last argument was the one selected in case search
            variables.append(XPathVariable(
                name=argument_ids[-1],
                xpath=CalculatedPropertyXPath(function=QuerySessionXPath(self.case_session_var).instance()),
            ))
        return variables

    @cached_property
    def endpoint_argument_ids(self):
        helper = EndpointsHelper(self.suite, self.app, [self.module])
        children = helper.get_frame_children(self.module, None)
        return helper.get_argument_ids(children)

    def _get_case_domain_xpath(self):
        case_id_xpath = CaseIDXPath(session_var(self.case_session_var))
        return case_id_xpath.case(instance_name=self.storage_instance).slash(COMMCARE_PROJECT)


class SessionEndpointRemoteRequestFactory(RemoteRequestFactory):
    def __init__(self, suite, module, detail_section_elements, endpoint_id, case_session_var):
        super().__init__(suite, module, detail_section_elements)
        self.endpoint_id = endpoint_id
        self.case_session_var = case_session_var

    def get_post_relevant(self):
        xpath = CaseClaimXpath(self.case_session_var)
        if self.module.is_multi_select():
            return xpath.multi_case_relevant()
        return xpath.default_relevant()

    def build_command(self):
        return Command(
            id=f"claim_command.{self.endpoint_id}.{self.case_session_var}",
            display=Display(text=Text()),   # users never see this, but a Display and Text are required
        )

    def build_remote_request_queries(self):
        return []

    def build_remote_request_datums(self):
        return [SessionDatum(
            id=self.case_session_var,
            function=QuerySessionXPath(self.case_session_var).instance(),
        )]

    def build_stack(self):
        return Stack()


class RemoteRequestsHelper(PostProcessor):
    """
    Adds a remote-request node, which sets the URL and query details for
    synchronous searching and case claiming.

    Search is available from the module's case list.

    See "remote-request" in the `CommCare 2.0 Suite Definition`_ for details.


    .. _CommCare 2.0 Suite Definition: https://github.com/dimagi/commcare/wiki/Suite20#remote-request

    """

    @time_method()
    def update_suite(self, detail_section_elements):
        for module in self.modules:
            if module_offers_search(module) and not module_uses_inline_search(module):
                self.suite.remote_requests.append(RemoteRequestFactory(
                    self.suite, module, detail_section_elements).build_remote_request()
                )
            if module.session_endpoint_id:
                self.suite.remote_requests.extend(
                    self.get_endpoint_contributions(module, None, module.session_endpoint_id,
                                                    detail_section_elements))

            if module.case_list_session_endpoint_id:
                self.suite.remote_requests.extend(
                    self.get_endpoint_contributions(module, None, module.case_list_session_endpoint_id,
                                                    detail_section_elements, False))

            for form in module.get_forms():
                if form.session_endpoint_id:
                    self.suite.remote_requests.extend(
                        self.get_endpoint_contributions(module, form, form.session_endpoint_id,
                                                        detail_section_elements))

    def get_endpoint_contributions(self, module, form, endpoint_id, detail_section_elements,
                                   should_add_last_selection_datum=True):
        helper = EndpointsHelper(self.suite, self.app, [module])
        children = helper.get_frame_children(module, form)
        elements = []
        for child in children:
            if isinstance(child, WorkflowDatumMeta) and child.requires_selection \
                    and (should_add_last_selection_datum or child != children[-1]):
                elements.append(SessionEndpointRemoteRequestFactory(
                    self.suite, module, detail_section_elements, endpoint_id, child.id).build_remote_request(),
                )
        return elements
