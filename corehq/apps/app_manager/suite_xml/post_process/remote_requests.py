from django.utils.functional import cached_property

from corehq import toggles
from corehq.apps.app_manager import id_strings
from corehq.apps.app_manager.suite_xml.contributors import (
    PostProcessor,
)
from corehq.apps.app_manager.suite_xml.post_process.endpoints import EndpointsHelper
from corehq.apps.app_manager.suite_xml.post_process.instances import (
    get_all_instances_referenced_in_xpaths,
)
from corehq.apps.app_manager.suite_xml.post_process.workflow import WorkflowDatumMeta
from corehq.apps.app_manager.suite_xml.sections.details import DetailsHelper
from corehq.apps.app_manager.suite_xml.xml_models import (
    CalculatedPropertyXPath,
    Command,
    Display,
    Hint,
    Instance,
    Itemset,
    PushFrame,
    QueryData,
    QueryPrompt,
    RemoteRequest,
    RemoteRequestPost,
    RemoteRequestQuery,
    RemoteRequestSession,
    SessionDatum,
    Stack,
    StackJump,
    Text,
    TextXPath,
    XPathVariable,
)
from corehq.apps.app_manager.util import (
    is_linked_app,
    module_offers_search,
    module_uses_smart_links,
)
from corehq.apps.app_manager.xpath import (
    CaseClaimXpath,
    CaseIDXPath,
    CaseTypeXpath,
    InstanceXpath,
    interpolate_xpath,
    session_var,
    XPath,
)
from corehq.apps.case_search.const import COMMCARE_PROJECT, EXCLUDE_RELATED_CASES_FILTER
from corehq.apps.case_search.models import (
    CASE_SEARCH_BLACKLISTED_OWNER_ID_KEY,
    CASE_SEARCH_REGISTRY_ID_KEY,
)
from corehq.util.timer import time_method
from corehq.util.view_utils import absolute_reverse

# The name of the instance where search results are stored
RESULTS_INSTANCE = 'results'

# The name of the instance where search results are stored when querying a data registry
REGISTRY_INSTANCE = 'registry'

SESSION_INSTANCE = 'commcaresession'


class QuerySessionXPath(InstanceXpath):
    id = SESSION_INSTANCE

    @property
    def path(self):
        return 'session/data/{}'.format(self)


class RemoteRequestFactory(object):
    def __init__(self, suite, module, detail_section_elements):
        self.suite = suite
        self.app = module.get_app()
        self.domain = self.app.domain
        self.module = module
        self.detail_section_elements = detail_section_elements
        self.case_session_var = self.module.search_config.case_session_var

    def build_remote_request(self):
        return RemoteRequest(
            post=self.build_remote_request_post(),
            command=self.build_command(),
            instances=self.build_instances(),
            session=self.build_session(),
            stack=self.build_stack(),
        )

    def build_remote_request_post(self):
        kwargs = {
            "url": absolute_reverse('claim_case', args=[self.domain]),
            "data": [
                QueryData(
                    key='case_id',
                    ref=QuerySessionXPath(self.case_session_var).instance(),
                ),
            ],
        }
        relevant = self.get_post_relevant()
        if relevant:
            kwargs["relevant"] = relevant
        return RemoteRequestPost(**kwargs)

    def get_post_relevant(self):
        return self.module.search_config.get_relevant()

    def build_command(self):
        return Command(
            id=id_strings.search_command(self.module),
            display=Display(
                text=Text(locale_id=id_strings.case_search_locale(self.module)),
            ),
        )

    def build_instances(self):
        prompt_select_instances = [
            Instance(id=prop.itemset.instance_id, src=prop.itemset.instance_uri)
            for prop in self.module.search_config.properties
            if prop.itemset.instance_id
        ]

        xpaths = {QuerySessionXPath(self.case_session_var).instance()}
        xpaths.update(datum.ref for datum in self._remote_request_query_datums)
        xpaths.add(self.module.search_config.get_relevant())
        xpaths.add(self.module.search_config.search_filter)
        xpaths.update(prop.default_value for prop in self.module.search_config.properties)
        # we use the module's case list/details view to select the datum so also
        # need these instances to be available
        xpaths.update(self._get_xpaths_for_module())
        instances, unknown_instances = get_all_instances_referenced_in_xpaths(self.app, xpaths)

        # exclude remote instances
        instances = [instance for instance in instances if 'remote' not in instance.src]

        # sorted list to prevent intermittent test failures
        return sorted(set(list(instances) + prompt_select_instances), key=lambda i: i.id)

    @cached_property
    def _details_helper(self):
        return DetailsHelper(self.app)

    def _get_xpaths_for_module(self):
        details_by_id = {detail.id: detail for detail in self.detail_section_elements}
        detail_ids = [self._details_helper.get_detail_id_safe(self.module, detail_type)
                      for detail_type, detail, enabled in self.module.get_details()
                      if enabled]
        detail_ids = [_f for _f in detail_ids if _f]
        for detail_id in detail_ids:
            yield from details_by_id[detail_id].get_all_xpaths()

    def build_session(self):
        return RemoteRequestSession(
            queries=self.build_remote_request_queries(),
            data=self.build_remote_request_datums(),
        )

    def build_remote_request_queries(self):
        return [
            RemoteRequestQuery(
                url=absolute_reverse('app_aware_remote_search', args=[self.app.domain, self.app._id]),
                storage_instance=RESULTS_INSTANCE,
                template='case',
                data=self._remote_request_query_datums,
                prompts=self.build_query_prompts(),
                default_search=self.module.search_config.default_search,
            )
        ]

    def build_remote_request_datums(self):
        if self.module.case_details.short.custom_xml:
            short_detail_id = 'case_short'
            long_detail_id = 'case_long'
        else:
            short_detail_id = 'search_short'
            long_detail_id = 'search_long'

        nodeset = CaseTypeXpath(self.module.case_type).case(instance_name=RESULTS_INSTANCE)
        if toggles.USH_CASE_CLAIM_UPDATES.enabled(self.app.domain):
            additional_types = list(set(self.module.search_config.additional_case_types) - {self.module.case_type})
            if additional_types:
                nodeset = CaseTypeXpath(self.module.case_type).cases(
                    additional_types, instance_name=RESULTS_INSTANCE)
            if self.module.search_config.search_filter:
                nodeset = f"{nodeset}[{interpolate_xpath(self.module.search_config.search_filter)}]"
        nodeset += EXCLUDE_RELATED_CASES_FILTER

        return [SessionDatum(
            id=self.case_session_var,
            nodeset=nodeset,
            value='./@case_id',
            detail_select=self._details_helper.get_detail_id_safe(self.module, short_detail_id),
            detail_confirm=self._details_helper.get_detail_id_safe(self.module, long_detail_id),
        )]

    @cached_property
    def _remote_request_query_datums(self):
        additional_types = set(self.module.search_config.additional_case_types) - {self.module.case_type}
        datums = [
            QueryData(key='case_type', ref=f"'{case_type}'")
            for case_type in [self.module.case_type] + list(additional_types)
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
        if self.module.search_config.data_registry:
            datums.append(
                QueryData(
                    key=CASE_SEARCH_REGISTRY_ID_KEY,
                    ref=f"'{self.module.search_config.data_registry}'",
                )
            )
        return datums

    def build_query_prompts(self):
        prompts = []
        for prop in self.module.search_config.properties:
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
            prompts.append(QueryPrompt(**kwargs))
        return prompts

    def build_stack(self):
        stack = Stack()
        rewind_if = None
        if module_uses_smart_links(self.module):
            user_domain_xpath = session_var(COMMCARE_PROJECT, path="user/data")
            # For case in same domain, do a regular case claim rewind
            rewind_if = self._get_case_domain_xpath().eq(user_domain_xpath)
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
        return case_id_xpath.case(instance_name=RESULTS_INSTANCE).slash(COMMCARE_PROJECT)


class SessionEndpointRemoteRequestFactory(RemoteRequestFactory):
    def __init__(self, suite, module, detail_section_elements, endpoint_id, case_session_var):
        super().__init__(suite, module, detail_section_elements)
        self.endpoint_id = endpoint_id
        self.case_session_var = case_session_var

    def get_post_relevant(self):
        return CaseClaimXpath(self.case_session_var).default_relevant()

    def build_command(self):
        return Command(
            id=f"claim_command.{self.endpoint_id}.{self.case_session_var}",
            display=Display(text=Text()),   # users never see this, but a Display and Text are required
        )

    def build_instances(self):
        query_xpaths = [QuerySessionXPath(self.case_session_var).instance()]
        query_xpaths.extend([datum.ref for datum in self._remote_request_query_datums])
        query_xpaths.append(self.get_post_relevant())
        instances, unknown_instances = get_all_instances_referenced_in_xpaths(self.app, query_xpaths)

        # sorted list to prevent intermittent test failures
        return sorted(instances, key=lambda i: i.id)

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
            if module_offers_search(module) or module_uses_smart_links(module):
                self.suite.remote_requests.append(RemoteRequestFactory(
                    self.suite, module, detail_section_elements).build_remote_request()
                )
            if module.session_endpoint_id:
                self.suite.remote_requests.extend(
                    self.get_endpoint_contributions(module, None, module.session_endpoint_id,
                                                    detail_section_elements))
            for form in module.get_forms():
                if form.session_endpoint_id:
                    self.suite.remote_requests.extend(
                        self.get_endpoint_contributions(module, form, form.session_endpoint_id,
                                                        detail_section_elements))

    def get_endpoint_contributions(self, module, form, endpoint_id, detail_section_elements):
        helper = EndpointsHelper(self.suite, self.app, [module])
        children = helper.get_frame_children(module, form)
        elements = []
        for child in children:
            if isinstance(child, WorkflowDatumMeta) and child.requires_selection:
                elements.append(SessionEndpointRemoteRequestFactory(
                    self.suite, module, detail_section_elements, endpoint_id, child.id).build_remote_request(),
                )
        return elements
