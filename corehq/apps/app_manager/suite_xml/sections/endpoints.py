from typing import List

from corehq.apps.app_manager import id_strings
from corehq.apps.app_manager.const import REGISTRY_WORKFLOW_SMART_LINK
from corehq.apps.app_manager.suite_xml.contributors import (
    SuiteContributorByModule,
)
from corehq.apps.app_manager.suite_xml.post_process.workflow import (
    CommandId,
    WorkflowDatumMeta,
    WorkflowHelper,
    prepend_parent_frame_children,
)
from corehq.apps.app_manager.suite_xml.xml_models import (
    Argument,
    PushFrame,
    SessionEndpoint,
    Stack,
    StackDatum,
)
from corehq.apps.app_manager.util import module_offers_search
from corehq.util.timer import time_method


class SessionEndpointContributor(SuiteContributorByModule):
    """
    Generates "Session Endpoints" - user-defined labels for forms or modules.
    They end up as entries in the suite file that declare stack operations
    necessary to navigate to the form or module, as well as what arguments (eg:
    case IDs) must be provided to get there.
    """

    @time_method()
    def get_module_contributions(self, module) -> List[SessionEndpoint]:
        endpoints = []
        if module.session_endpoint_id:
            endpoints.append(self._make_session_endpoint(module))
        if module.module_type != "shadow":
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
        helper = EndpointsHelper(self.suite, self.app)
        children = helper.get_frame_children(module, form)
        argument_ids = self._get_argument_ids(children)

        # Add a claim request for each endpoint argument.
        # This assumes that all arguments are case ids.
        for arg_id in argument_ids:
            self._add_claim_frame(stack, arg_id, endpoint_id)

        # Add a frame to navigate to the endpoint
        frame = PushFrame()
        stack.add_frame(frame)
        for child in children:
            if isinstance(child, CommandId):
                frame.add_command(child.to_command())
            elif child.id in argument_ids:
                self._add_datum_for_arg(frame, child.id)

        kwargs = {
            "id": endpoint_id,
            "arguments": [Argument(id=i) for i in argument_ids],
            "stack": stack,
        }
        if module_offers_search(module):
            if module.search_config.data_registry_workflow == REGISTRY_WORKFLOW_SMART_LINK:
                kwargs["command_id"] = id_strings.form_command(form) if form else id_strings.menu_id(module)
        return SessionEndpoint(**kwargs)

    def _get_argument_ids(self, frame_children):
        return [
            child.id for child in frame_children
            if isinstance(child, WorkflowDatumMeta) and child.requires_selection
        ]

    def _add_claim_frame(self, stack, arg_id, endpoint_id):
        frame = PushFrame()
        stack.add_frame(frame)
        self._add_datum_for_arg(frame, arg_id)
        frame.add_command(f"'claim_command.{endpoint_id}.{arg_id}'")

    def _add_datum_for_arg(self, frame, arg_id):
        frame.add_datum(
            StackDatum(id=arg_id, value=f"${arg_id}")
        )


class EndpointsHelper(object):
    def __init__(self, suite, app):
        self.suite = suite
        self.app = app

    def get_frame_children(self, module, form):
        helper = WorkflowHelper(self.suite, self.app, self.app.get_modules())
        frame_children = helper.get_frame_children(module, form)
        if module.root_module_id:
            frame_children = prepend_parent_frame_children(helper, frame_children, module.root_module)
        return frame_children
