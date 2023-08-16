"""
EndpointsHelper
---------------

This is support for session endpoints, which are a flagged feature for mobile that also form the basis of smart
links in web apps.

Endpoints define specific locations in the application using a stack, so they rely on similar logic to end of form
navigation. The complexity of generating endpoints is all delegated to ``WorkflowHelper``.
"""
from corehq.apps.app_manager.suite_xml.contributors import PostProcessor
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
from corehq.util.timer import time_method


class EndpointsHelper(PostProcessor):
    """
    Generates "Session Endpoints" - user-defined labels for forms or modules.
    They end up as entries in the suite file that declare stack operations
    necessary to navigate to the form or module, as well as what arguments (eg:
    case IDs) must be provided to get there.
    """

    @time_method()
    def update_suite(self):
        for module in self.modules:
            if module.session_endpoint_id:
                self.suite.endpoints.append(self._make_session_endpoint(module.session_endpoint_id, module))
            if module.case_list_session_endpoint_id:
                self.suite.endpoints.append(self._make_session_endpoint(
                    module.case_list_session_endpoint_id, module, None, False))
            if module.module_type != "shadow":
                for form in module.get_suite_forms():
                    if form.session_endpoint_id:
                        self.suite.endpoints.append(self._make_session_endpoint(
                            form.session_endpoint_id, module, form))
            elif module.session_endpoint_id:
                for form in module.get_suite_forms():
                    endpoint = next(
                        (m for m in module.form_session_endpoints if m.form_id == form.unique_id), None)
                    if endpoint:
                        self.suite.endpoints.append(self._make_session_endpoint(
                            endpoint.session_endpoint_id, module, form))

    def _make_session_endpoint(self, endpoint_id, module, form=None, should_add_last_selection_datum=True):
        stack = Stack()
        children = self.get_frame_children(module, form)
        argument_ids = self.get_argument_ids(children, form, should_add_last_selection_datum)

        # Add a claim request for each endpoint argument.
        # This assumes that all arguments are case ids.
        non_computed_argument_ids = [
            child.id for child in children
            if isinstance(child, WorkflowDatumMeta) and child.requires_selection
            and (should_add_last_selection_datum or child != children[-1])
        ]
        for arg_id in non_computed_argument_ids:
            self._add_claim_frame(stack, arg_id, endpoint_id)

        # Add a frame to navigate to the endpoint
        frame = PushFrame()
        stack.add_frame(frame)
        for child in children:
            if isinstance(child, CommandId):
                frame.add_command(child.to_command())
            elif child.id in argument_ids:
                self._add_datum_for_arg(frame, child.id)

        return SessionEndpoint(
            id=endpoint_id,
            arguments=[Argument(id=i) for i in argument_ids],
            stack=stack,
        )

    def get_argument_ids(self, frame_children, form=None, should_add_last_selection_datum=True):

        def should_include(child, add_selection_datum):
            if not isinstance(child, WorkflowDatumMeta):
                return False
            if child.requires_selection and add_selection_datum:
                return True
            if form:
                return child.id in (form.function_datum_endpoints or [])
            return False

        return [
            child.id for child in frame_children
            if should_include(child, should_add_last_selection_datum or child != frame_children[-1])
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

    def get_frame_children(self, module, form):
        helper = WorkflowHelper(self.suite, self.app, self.app.get_modules())
        frame_children = helper.get_frame_children(module, form)
        if module.root_module_id:
            frame_children = prepend_parent_frame_children(helper, frame_children, module.root_module)
        return frame_children
