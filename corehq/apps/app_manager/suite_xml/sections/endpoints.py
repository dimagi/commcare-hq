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
            endpoints.append(self._get_endpoint(module=module))
        for form in module.get_suite_forms():
            if form.session_endpoint_id:
                endpoints.append(self._get_endpoint(form=form, module=module))
        return endpoints

    def _get_module_endpoint(self, module):
        id_string = id_strings.case_list_command(module)
        return self._make_session_endpoint(id_string, module, module.session_endpoint_id)

    def _get_form_endpoint(self, form, module):
        id_string = id_strings.form_command(form)
        return self._make_session_endpoint(id_string, module, form.session_endpoint_id)

    def _get_endpoint(self, form=None, module=None):
        is_form = form is not None

        arguments = []
        commands = []
        datums = []
        id_string = id_strings.form_command(form) if is_form else id_strings.case_list_command(module)
        if not is_form:
            commands.append(XPath.string(id_string))
        helper = WorkflowHelper(self.suite, self.app, self.modules)
        for child in helper.get_frame_children(id_string, module):
            if isinstance(child, WorkflowDatumMeta):
                arguments.append(Argument(id=child.id))
                datums.append(StackDatum(id=child.id, value=f"${child.id}"))
            elif is_form:
                commands.append(XPath.string(child.id))

        stack = Stack()
        frame = PushFrame()
        stack.add_frame(frame)
        for command in commands:
            frame.add_command(command)
        for datum in datums:
            frame.add_datum(datum)

        return SessionEndpoint(
            id=form.session_endpoint_id if is_form else module.session_endpoint_id,
            arguments=arguments,
            stack=stack,
        )
