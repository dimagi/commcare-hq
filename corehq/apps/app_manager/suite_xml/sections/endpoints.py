from typing import List

from corehq.apps.app_manager import id_strings
from corehq.apps.app_manager.suite_xml.contributors import (
    SuiteContributorByModule,
)
from corehq.apps.app_manager.suite_xml.xml_models import (
    Argument,
    PushFrame,
    SessionEndpoint,
    Stack, StackDatum,
)
from corehq.apps.app_manager.xpath import XPath, session_var


class SessionEndpointContributor(SuiteContributorByModule):

    def get_module_contributions(self, module) -> List[SessionEndpoint]:
        endpoints = []
        if module.session_endpoint_ids:
            endpoints.append(_get_module_endpoint(module))
        for form in module.get_suite_forms():
            if form.session_endpoint_ids:
                endpoints.append(_get_form_endpoint(form))
        return endpoints


def _get_module_endpoint(module) -> SessionEndpoint:
    id_string = id_strings.case_list_command(module)
    return SessionEndpoint(
        arguments=[Argument(id=id_) for id_ in module.session_endpoint_ids],
        stack=_build_stack(id_string, module.session_endpoint_ids),
    )


def _get_form_endpoint(form) -> SessionEndpoint:
    id_string = id_strings.form_command(form)
    return SessionEndpoint(
        arguments=[Argument(id=id_) for id_ in form.session_endpoint_ids],
        stack=_build_stack(id_string, form.session_endpoint_ids),
    )


def _build_stack(id_string: str, endpoint_ids: List[str]) -> Stack:
    """
    Returns a stack with the command for a form or case list, and a list
    of datums whose ID and session variable name are both the element ID.

    .. note::
       This assumes that the session variable name and the datum ID
       should be the same.

    e.g. ::

        <stack>
          <push>
            <command value="'m1-f0'"/>
            <datum id="case_id" value="instance('commcaresession')/session/data/case_id"/>
          </push>
        </stack>

    """
    stack = Stack()
    frame = PushFrame()
    frame.add_command(XPath.string(id_string))
    for endpoint_id in endpoint_ids:
        frame.add_datum(StackDatum(
            id=endpoint_id,
            value=session_var(endpoint_id))
        )
    stack.add_frame(frame)
    return stack
