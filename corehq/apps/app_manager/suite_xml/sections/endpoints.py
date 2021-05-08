from typing import List

from corehq.apps.app_manager import id_strings
from corehq.apps.app_manager.suite_xml.contributors import (
    SuiteContributorByModule,
)
from corehq.apps.app_manager.suite_xml.post_process.workflow import (
    WorkflowDatumMeta,
    WorkflowHelper,
)
from corehq.apps.app_manager.suite_xml.xml_models import (
    Argument,
    PushFrame,
    SessionEndpoint,
    Stack,
    StackDatum,
)
from corehq.apps.app_manager.xpath import XPath


class SessionEndpointContributor(SuiteContributorByModule):
    """
    Generates "Session Endpoints" - user-defined labels for forms or modules.
    They end up as entries in the suite file that declare stack operations
    necessary to navigate to the form or module, as well as what arguments (eg:
    case IDs) must be provided to get there.
    """

    def get_module_contributions(self, module) -> List[SessionEndpoint]:
        endpoints = []
        if module.session_endpoint_id:
            endpoints.append(self._get_module_endpoint(module))
        for form in module.get_suite_forms():
            if form.session_endpoint_id:
                endpoints.append(self._get_form_endpoint(form, module))
        return endpoints

    def _get_module_endpoint(self, module):
        id_string = id_strings.case_list_command(module)
        return self._make_session_endpoint(id_string, module, module.session_endpoint_id)

    def _get_form_endpoint(self, form, module):
        id_string = id_strings.form_command(form)
        return self._make_session_endpoint(id_string, module, form.session_endpoint_id)

    def _make_session_endpoint(self, id_string, module, endpoint_id):
        stack = Stack()
        frame = PushFrame()
        stack.add_frame(frame)
        frame.add_command(XPath.string(id_string))
        arguments = []
        helper = WorkflowHelper(self.suite, self.app, self.modules)
        for child in helper.get_frame_children(id_string, module):
            if isinstance(child, WorkflowDatumMeta):
                arguments.append(Argument(id=child.id))
                frame.add_datum(
                    StackDatum(id=child.id, value=f"${child.id}")
                )

        return SessionEndpoint(
            id=endpoint_id,
            arguments=arguments,
            stack=stack,
        )
