from typing import List

from corehq.apps.app_manager import id_strings
from corehq.apps.app_manager.suite_xml.contributors import (
    SuiteContributorByModule,
)
from corehq.apps.app_manager.suite_xml.post_process.workflow import (
    CommandId,
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
            endpoints.append(self._make_session_endpoint(module))
        for form in module.get_suite_forms():
            if form.session_endpoint_id:
                endpoints.append(self._make_session_endpoint(module, form))
        return endpoints

    def _make_session_endpoint(self, module, form=None):
        if form is not None:
            endpoint_id = form.session_endpoint_id
        else:
            endpoint_id = module.session_endpoint_id

        stack = Stack()
        frame = PushFrame()
        stack.add_frame(frame)
        arguments = []
        helper = WorkflowHelper(self.suite, self.app, self.modules)
        for child in helper.get_frame_children(module, form, include_root_module=True):
            if isinstance(child, WorkflowDatumMeta):
                arguments.append(Argument(id=child.id))
                frame.add_datum(
                    StackDatum(id=child.id, value=f"${child.id}")
                )
            elif isinstance(child, CommandId):
                frame.add_command(child.to_command())

        return SessionEndpoint(
            id=endpoint_id,
            arguments=arguments,
            stack=stack,
        )
