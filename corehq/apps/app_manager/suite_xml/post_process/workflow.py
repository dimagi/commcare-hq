"""
WorkflowHelper
--------------

This is primarily used for end of form navigation and form linking.
It contains logic to determine the proper sequence of commands to navigate a particular place in an app, such as a
specific case list. It also needs to provide any datums required to reach that place in the app.

Because CommCare's UI logic is driven by the data currently in the user's session and the data
needed by forms, rather than being directly configured, this means HQ needs to predict how CommCare's UI logic will
behave, which is difficult and results in code that's easily disturbed by new features that influence
navigation.

Understanding stacks in the `CommCare Session <https://github.com/dimagi/commcare-core/wiki/SessionStack>`_ is
useful for working with ``WorkflowHelper``.

Some areas to be aware of:

* Datums can either require manual selection (from a case list) or can be automatically selected (such as the
  usercase id).
* HQ names each datum, defaulting to ``case_id`` for datums selected from case lists.
  When HQ determines that a form requires multiple datums, it creates a new id for the new datum, which will often
  incorporate the case type. It also may need to rename datums that already exist - see
  ``_replace_session_references_in_stack``.
* To determine which datums are distinct and which represent the same piece of information, HQ has matching logic
  in ``_find_best_match``.
* ``get_frame_children`` generates the list of frame children that will navigate to a given form or module,
  mimicking CommCare's navigation logic
* Shadow modules complicate this entire area, because they use their source module's forms but their own module
  configuration.
* There are a bunch of advanced features with their own logic, such as advanced modules, but even the basic logic
  is fairly complex.
* Within end of form navigation and form linking, the "previous screen" option is the most fragile. Form linking
  has simpler code, since it pushes the complexity of the feature onto app builders.

"""
import re
from collections import defaultdict, namedtuple
from functools import total_ordering
from os.path import commonprefix
from xml.sax.saxutils import unescape

from memoized import memoized

from corehq.apps.app_manager import id_strings
from corehq.apps.app_manager.const import (
    RETURN_TO,
    WORKFLOW_FORM,
    WORKFLOW_MODULE,
    WORKFLOW_PARENT_MODULE,
    WORKFLOW_PREVIOUS,
    WORKFLOW_ROOT,
)
from corehq.apps.app_manager.exceptions import SuiteValidationError, SuiteError
from corehq.apps.app_manager.suite_xml.contributors import PostProcessor
from corehq.apps.app_manager.suite_xml.xml_models import (
    CreateFrame,
    Stack,
    StackDatum,
    SessionDatum,
    InstanceDatum,
    RemoteRequestQuery,
    StackQuery,
    QueryData,
)
from corehq.apps.app_manager.xpath import (
    CaseIDXPath,
    XPath,
    session_var,
    SearchSelectedCasesInstanceXpath
)
from corehq.apps.case_search.models import CASE_SEARCH_REGISTRY_ID_KEY
from corehq.util.timer import time_method


class WorkflowHelper(PostProcessor):

    def __init__(self, suite, app, modules):
        super(WorkflowHelper, self).__init__(suite, app, modules)

    @property
    @memoized
    def _root_module_datums(self):
        root_modules = [module for module in self.modules if module.put_in_root]
        return [
            datum for module in root_modules
            for datum in self.get_module_datums('m{}'.format(module.id)).values()
        ]

    @time_method()
    def update_suite(self):
        """
        Add stack elements to form entry elements to configure app workflow. This updates
        the Entry objects in place.
        """
        for module in self.modules:
            for form in module.get_suite_forms():
                frames = self._get_stack_frames(form, module)
                if frames:
                    entry = self._get_form_entry(id_strings.form_command(form, module))
                    self._add_frames_to_entry(entry, frames)

    def _get_stack_frames(self, form, module):
        end_of_form_frames = EndOfFormNavigationWorkflow(self).form_workflow_frames(module, form)
        if end_of_form_frames:
            stack_frames = end_of_form_frames
        else:
            stack_frames = CaseListFormWorkflow(self).case_list_forms_frames(form)

        return [_f for _f in [meta.to_frame() for meta in stack_frames if meta is not None] if _f]

    @staticmethod
    def _add_frames_to_entry(entry, frames):
        if not entry.stack:
            entry.stack = Stack()
        for frame in frames:
            entry.stack.add_frame(frame)

    @staticmethod
    def _get_id_suffix(module):
        from corehq.apps.app_manager.models import ShadowModule

        root_module = None
        if not module.put_in_root:
            if module.root_module:
                root_module = module.root_module
            elif module.module_type == 'shadow' and module.source_module.root_module:
                root_module = module.source_module.root_module

        suffix = id_strings.menu_id(root_module) if isinstance(root_module, ShadowModule) else ""
        return suffix

    def get_frame_children(self, module, form=None, include_root_module=False):
        """
        For a form or module return the list of stack frame children that are required
        to navigate there; a mix of commands and datum declarations.

        This is based on the following algorithm:

        * Add the module (or form's module) to the stack (we'll call this `m`)
        * Walk through all forms in the module, determine what datum selections
          are present in all of the forms (this may be an empty set)
          * Basically if there are three forms that respectively load
            * f1: v1, v2, v3, v4
            * f2: v1, v2, v4
            * f3: v1, v2
          * The longest common chain is v1, v2
        * Add a datum for each of those values to the stack

        For forms:
        * Add the form "command id" for the <entry> to the stack
        * Add the remainder of the datums for the current form to the stack
        * For the three forms above, the stack entries for "last element" would be
          * m, v1, v2, f1, v3, v4
          * m, v1, v2, f2, v4
          * m, v1, v2, f3

        :returns:   list of strings and DatumMeta objects. String represent stack commands
                    and DatumMeta's represent stack datums.
        """
        module_command = id_strings.menu_id(module, WorkflowHelper._get_id_suffix(module))
        if form is None and module.module_type == "shadow":
            module_datums = self.get_module_datums(f'm{module.source_module.id}')
        else:
            module_datums = self.get_module_datums(f'm{module.id}')

        frame_children = []
        if module_command == id_strings.ROOT:
            datums_list = self._root_module_datums
        else:
            datums_list = list(module_datums.values())  # [ [datums for f0], [datums for f1], ...]
            root_module = module.root_module
            if root_module and include_root_module:
                datums_list.extend(self.get_module_datums(id_strings.menu_id(root_module)).values())
                root_module_command = id_strings.menu_id(root_module)
                if root_module_command != id_strings.ROOT:
                    frame_children.append(CommandId(root_module_command))
            frame_children.append(CommandId(module_command))

        common_datums = commonprefix(datums_list)
        frame_children.extend(common_datums)

        if form:
            frame_children.append(CommandId(id_strings.form_command(form, module)))
            form_datums = module_datums[f'f{form.id}']
            remaining_datums = form_datums[len(common_datums):]
            frame_children.extend(remaining_datums)

        return frame_children

    def get_form_datums(self, form):
        """
        :return: List of DatumMeta objects for this form
        """
        module_id, form_id = id_strings.form_command(form).split('-')
        return self.get_module_datums(module_id)[form_id]

    def get_module_datums(self, module_id):
        """
        :return: Dictionary keyed by form ID containing list of DatumMeta objects for each form.
        """
        _, datums = self._get_entries_datums()
        return datums[module_id]

    def _get_form_entry(self, form_command):
        entries, _ = self._get_entries_datums()
        return entries[form_command]

    @memoized
    def _get_entries_datums(self):
        datums = defaultdict(lambda: defaultdict(list))
        entries = {}

        def _include_datums(entry):
            # might want to make this smarter in the future, but for now just hard-code
            # formats that we know we don't need or don't work
            return not entry.command.id.startswith('reports') and not entry.command.id.endswith('case-list')

        for e in filter(_include_datums, self.suite.entries):
            command = e.command.id
            module_id, form_id = command.split('-', maxsplit=1)
            entries[command] = e
            if not e.session_children:
                datums[module_id][form_id] = []
            else:
                session_children = list(e.session_children)
                for index, d in enumerate(session_children):
                    next_index = index + 1
                    next_meta = (
                        workflow_meta_from_session_datum(session_children[next_index], None)
                        if next_index < len(session_children) else None
                    )
                    if next_meta and not next_meta.case_type:
                        self._add_missing_case_types(module_id, form_id, [next_meta])
                    datums[module_id][form_id].append(workflow_meta_from_session_datum(d, next_meta))

        for module_id, form_datum_map in datums.items():
            for form_id, entry_datums in form_datum_map.items():
                self._add_missing_case_types(module_id, form_id, entry_datums)

        return entries, datums

    @memoized
    def _form_datums(self, module_id, form_id):
        module_id = module_id[1:]  # strip 'm'
        form_id = form_id[1:]  # strip 'f'
        module = self.app.get_module(module_id)
        if module.module_type == 'shadow':
            module = module.source_module

        if not module:
            return {}
        form = module.get_form(form_id)
        if not form:
            return {}
        return {d.id: d for d in self.entries_helper.get_datums_meta_for_form_generic(form)}

    def _add_missing_case_types(self, module_id, form_id, entry_datums):
        form_datums_by_id = self._form_datums(module_id, form_id)
        for entry_datum in entry_datums:
            if not entry_datum.case_type:
                form_datum = form_datums_by_id.get(entry_datum.id)
                if form_datum:
                    entry_datum.case_type = form_datum.case_type
                    entry_datum.from_parent_module = form_datum.from_parent


def _get_datums_matched_to_manual_values(target_frame_elements, manual_values, form):
    """
    Attempt to match the target session variables with ones that the user
    has entered manually
    """
    manual_values_by_name = {datum.name: datum.xpath for datum in manual_values}
    for child in target_frame_elements:
        if child.id in manual_values_by_name:
            yield StackDatum(id=child.id, value=manual_values_by_name.get(child.id))
        elif not isinstance(child, WorkflowSessionMeta) or not child.requires_selection:
            yield child
        else:
            raise SuiteValidationError("Unable to link form '{}', missing variable '{}'".format(
                form.default_name(), child.id
            ))


def _get_datums_matched_to_source(target_frame_elements, source_datums):
    """
    Attempt to match the target session variables with ones in the source session.
    Making some large assumptions about how people will actually use this feature
    """
    unused_source_datums = list(source_datums)
    for target_datum in target_frame_elements:
        if isinstance(target_datum, WorkflowQueryMeta) and isinstance(target_datum.next_datum, WorkflowDatumMeta):
            next_datum = target_datum.next_datum
            if target_datum.is_case_search and next_datum.requires_selection:
                # This query is populating an instance which will be used by the next datum
                # so we need to use the correct case_id session var
                # see RemoteRequestSuiteTest.test_form_linking_to_registry_module
                match = _find_best_match(next_datum, unused_source_datums)
                if match:
                    target_datum = target_datum.clone_to_match(match.source_id)
            yield target_datum
        elif not isinstance(target_datum, WorkflowSessionMeta) or not target_datum.requires_selection:
            yield target_datum
        else:
            match = _find_best_match(target_datum, unused_source_datums)
            if match:
                unused_source_datums = [datum for datum in unused_source_datums if datum.id != match.id]

            yield match if match else target_datum


def _find_best_match(target_datum, source_datums):
    """Find the datum in the list of source datums that best matches the target datum (if any)

    This uses the datums ID and case type to match. If 'additional_case_types' are in use then the matching
    can still work since the datums will have their case type set to their module's case type. A caveat
    here is that it is possible to link a form with multiple case types to a form that only supports
    one of the case types. This is not disabled since the app builder could configure conditional linking.
    """
    candidate = None
    for source_datum in source_datums:
        if isinstance(source_datum, WorkflowQueryMeta):
            continue
        if source_datum.from_parent_module:
            # if the datum is only there as a placeholder then we should ignore it
            continue
        if target_datum.id == source_datum.id:
            if source_datum.case_type and source_datum.case_type == target_datum.case_type:
                # same ID, same case type
                candidate = target_datum
                break
        else:
            if source_datum.case_type and source_datum.case_type == target_datum.case_type:
                # different ID, same case type
                candidate = target_datum.clone_to_match(source_id=source_datum.id)
                break

    return candidate


class EndOfFormNavigationWorkflow(object):

    def __init__(self, helper):
        self.helper = helper

    def form_workflow_frames(self, module, form):
        """
        post_form_workflow = 'module':
          * Add stack frame and a command with value = "module command"

        post_form_workflow = 'previous_screen':
          * Add stack frame and a command with value = "module command"
          * Find longest list of common datums between form entries for the module and add datums
            to the stack frame for each.
          * Add a command to the frame with value = "form command"
          * Add datums to the frame for any remaining datums for that form.
          * Remove any autoselect items from the end of the stack frame.
          * Finally remove the last item from the stack frame.
        """
        if form.post_form_workflow != WORKFLOW_FORM:
            static_stack_frame = self._get_static_stack_frame(form.post_form_workflow, form, module)
            return [static_stack_frame] if static_stack_frame else []

        stack_frames = []
        for link in form.form_links:
            stack_frames.append(self._get_link_frame(link, form, module))

        fallback_frame = self._get_fallback_frame(form, module)
        if fallback_frame:
            stack_frames.append(fallback_frame)

        return stack_frames

    def _get_static_stack_frame(self, form_workflow, form, module, xpath=None):
        if form_workflow == WORKFLOW_ROOT:
            return StackFrameMeta(xpath, [], allow_empty_frame=True)
        elif form_workflow == WORKFLOW_MODULE:
            frame_children = self._frame_children_for_module(module, include_user_selections=False)
            return StackFrameMeta(xpath, frame_children)
        elif form_workflow == WORKFLOW_PARENT_MODULE:
            root_module = module.root_module
            frame_children = self._frame_children_for_module(root_module)
            return StackFrameMeta(xpath, frame_children)
        elif form_workflow == WORKFLOW_PREVIOUS:
            frame_children = self.helper.get_frame_children(module, form, include_root_module=True)

            # since we want to go the 'previous' screen we need to drop the last
            # datum
            last = frame_children.pop()
            while isinstance(last, WorkflowSessionMeta) and not last.requires_selection:
                # keep removing last element until we hit a command
                # or a non-autoselect datum
                last = frame_children.pop()

            return StackFrameMeta(xpath, frame_children)

    def _frame_children_for_module(self, module, include_user_selections=True):
        frame_children = []
        if module.root_module:
            frame_children.extend(self._frame_children_for_module(module.root_module))

        if include_user_selections:
            this_module_children = self.helper.get_frame_children(module)
            for child in this_module_children:
                if child not in frame_children:
                    frame_children.append(child)
        else:
            module_command = id_strings.menu_id(module, WorkflowHelper._get_id_suffix(module))
            if module_command != id_strings.ROOT:
                frame_children.append(CommandId(module_command))

        return frame_children

    def _get_link_frame(self, link, form, module):
        source_form_datums = self.helper.get_form_datums(form)
        if link.form_id:
            target_form = self.helper.app.get_form(link.form_id)
            if link.form_module_id:
                target_module = self.helper.app.get_module_by_unique_id(link.form_module_id)
            else:
                target_module = target_form.get_module()
            if module.module_type == "shadow" and module.source_module_id == target_module.unique_id:
                # If this is a shadow module and we're navigating to a form from the source module,
                # presume we should navigate to the version of the form in the current (shadow) module.
                # This only affects breadcrumbs.
                target_module = module
            target_frame_children = self.helper.get_frame_children(target_module, target_form)
        elif link.module_unique_id:
            target_module = self.helper.app.get_module_by_unique_id(link.module_unique_id)
            target_frame_children = self._frame_children_for_module(target_module, include_user_selections=False)

        if link.datums:
            frame_children = _get_datums_matched_to_manual_values(target_frame_children, link.datums, form)
        else:
            frame_children = _get_datums_matched_to_source(target_frame_children, source_form_datums)

        if target_module.root_module_id:
            root_module = self.helper.app.get_module_by_unique_id(target_module.root_module_id)
            frame_children = prepend_parent_frame_children(
                self.helper, frame_children, root_module, link.datums, form)

        return StackFrameMeta(link.xpath, list(frame_children), current_session=source_form_datums)

    def _get_fallback_frame(self, form, module):
        if form.post_form_workflow_fallback:
            # If no form link's xpath conditions are met, use the fallback
            conditions = [link.xpath for link in form.form_links if link.xpath.strip()]
            if conditions:
                no_conditions_match = ' and '.join(f'not({condition})' for condition in conditions)
                return self._get_static_stack_frame(
                    form.post_form_workflow_fallback, form, module, xpath=no_conditions_match
                )


def prepend_parent_frame_children(helper, frame_children, parent_module, manual_values=None, form=None):
    # Note: this fn is roughly equivalent to just passing include_root_module
    # to get_frame_children in the first place, but that gives the wrong order
    parent_frame_children = helper.get_frame_children(parent_module)
    if manual_values:
        parent_frame_children = list(
            _get_datums_matched_to_manual_values(parent_frame_children, manual_values, form)
        )

    parent_ids = {parent.id for parent in parent_frame_children}
    return parent_frame_children + [
        child for child in frame_children
        if child.id not in parent_ids
    ]


class CaseListFormStackFrames(namedtuple('CaseListFormStackFrames', 'case_created case_not_created')):
    """Class that represents the two stack create blocks generated for Case List Form Actions.
    """
    source_session_var = None

    def add_children(self, children):
        children = list(children)
        if self.case_created:
            for child in children:
                self.case_created.add_child(child)
        for child in children:
            if not isinstance(child, WorkflowDatumMeta) or child.source_id != self.source_session_var:
                # add all children to the 'case not created' block unless it's the datum of the
                # case that was supposed to be created by the form, or a later datum
                self.case_not_created.add_child(child)
            else:
                break

    @property
    def ids_on_stack(self):
        """All ID's that are already part the stack block"""
        if self.case_created:
            return {child.id for child in self.case_created.children}
        else:
            return set()


class CaseListFormWorkflow(object):

    def __init__(self, helper):
        self.helper = helper

    def case_list_forms_frames(self, form):
        if not form.is_case_list_form:
            return []

        stack_frames = []
        for target_module in form.case_list_modules:
            target_case_type = target_module.case_type
            if not form.is_registration_form(target_case_type):
                continue

            stack_frames.extend(self.get_stack_frames_for_case_list_form_target(target_module, form))

        return stack_frames

    def get_stack_frames_for_case_list_form_target(self, target_module, form):
        source_form_datums = self.helper.get_form_datums(form)
        stack_frames = self._get_stack_frames(target_module, form, source_form_datums)

        if target_module.root_module_id:
            # add stack children for the root module before adding any for the child module.
            self._add_stack_children_for_target(stack_frames, target_module.root_module, source_form_datums)

        self._add_stack_children_for_target(stack_frames, target_module, source_form_datums)
        return stack_frames

    def _add_stack_children_for_target(self, stack_frames, target_module, source_form_datums):
        """
        :param stack_frames: Stack to add children to
        :param target_module: Module that we're targeting for navigating to
        :param source_form_datums: List of datums from the source form.
        """
        ids_on_stack = stack_frames.ids_on_stack

        if target_module.forms or (target_module.case_list and target_module.case_list.show):
            target_frame_children = self.helper.get_frame_children(target_module)
            remaining_target_frame_children = [fc for fc in target_frame_children if fc.id not in ids_on_stack]
            frame_children = _get_datums_matched_to_source(
                remaining_target_frame_children, source_form_datums
            )
            stack_frames.add_children(frame_children)

    def _get_stack_frames(self, target_module, form, source_form_datums):
        """
        Set up the stack blocks for a single case list form action.
        :param target_module: Module that the user is returning to
        :param form: Case list form
        :param source_form_datums: List of datum from the case list form
        :return: CaseListFormStackFrames object
        """
        from corehq.apps.app_manager.const import WORKFLOW_CASE_LIST
        source_session_var = self._get_source_session_var(form, target_module.case_type)
        source_case_id = session_var(source_session_var)
        case_count = CaseIDXPath(source_case_id).case().count()
        target_command = id_strings.menu_id(target_module)

        if target_module.case_list_form.post_form_workflow == WORKFLOW_CASE_LIST:
            frame_case_created = None
            frame_case_not_created = StackFrameMeta(
                self.get_if_clause(None, target_command), current_session=source_form_datums
            )
        else:
            frame_case_created = StackFrameMeta(
                self.get_if_clause(case_count.gt(0), target_command), current_session=source_form_datums
            )
            frame_case_not_created = StackFrameMeta(
                self.get_if_clause(case_count.eq(0), target_command), current_session=source_form_datums
            )

        stack_frames = CaseListFormStackFrames(
            case_created=frame_case_created, case_not_created=frame_case_not_created
        )
        stack_frames.source_session_var = source_session_var
        return stack_frames

    @staticmethod
    def _get_source_session_var(form, target_case_type):
        if form.form_type == 'module_form':
            [reg_action] = form.get_registration_actions(target_case_type)
            source_session_var = form.session_var_for_action(reg_action)
        if form.form_type == 'advanced_form' or form.form_type == "shadow_form":
            # match case session variable
            reg_action = form.get_registration_actions(target_case_type)[0]
            source_session_var = reg_action.case_session_var
        return source_session_var

    @staticmethod
    def get_target_dm(target_form_dm, case_type, module):
        """Find the datum from the target form with the specified case type.
        """
        try:
            [target_dm] = [
                target_meta for target_meta in target_form_dm
                if getattr(target_meta, 'case_type', None) == case_type
            ]
        except ValueError:
            # This either means that the source module (with the registration form) requires datums that the
            # target module (the module which called the reg form).
            # OR it could mean that not all the forms in the target module have the same case management
            # configuration.
            return
        return target_dm

    @staticmethod
    def get_if_clause(case_count_xpath, target_command):
        return_to = session_var(RETURN_TO)
        args = [
            return_to.count().eq(1),
            return_to.eq(XPath.string(target_command)),
        ]
        if case_count_xpath:
            args.append(case_count_xpath)
        return XPath.and_(*args)

    @staticmethod
    def get_case_type_created_by_form(form, target_module):
        if form.form_type == 'module_form':
            [reg_action] = form.get_registration_actions(target_module.case_type)
            if reg_action == 'open_case':
                return form.get_module().case_type
            else:
                return reg_action.case_type
        elif form.form_type == 'advanced_form' or form.form_type == "shadow_form":
            return form.get_registration_actions(target_module.case_type)[0].case_type


class StackFrameMeta(object):
    """
    Class used in computing the form workflow.
    """

    def __init__(self, if_clause, children=None, allow_empty_frame=False, current_session=None):
        """
        :param if_clause: XPath expression to use in if clause for CreateFrame
        :type if_clause: string
        :param children: Child elements for the frame
        :type children: list
        :param allow_empty_frame: True if the frame can be empty
        :type allow_empty_frame: bool
        :param current_session: List of current session datums
        :type current_session: list of WorkflowDatumMeta
        """
        self.current_session = current_session
        self.if_clause = unescape(if_clause) if if_clause else None
        self.children = []
        self.allow_empty_frame = allow_empty_frame

        if children:
            for child in children:
                self.add_child(child)

    def add_child(self, child):
        if isinstance(child, WorkflowSessionMeta):
            child = child.to_stack_datum()
        self.children.append(child)

    def to_frame(self):
        if not self.children and not self.allow_empty_frame:
            return

        children = _replace_session_references_in_stack(self.children, current_session=self.current_session)

        frame = CreateFrame(if_clause=self.if_clause)

        for child in children:
            if isinstance(child, CommandId):
                frame.add_command(child.to_command())
            elif isinstance(child, (StackDatum, StackQuery)):
                frame.add_datum(child)
            else:
                raise SuiteError("Unexpected child type: {} ({})".format(type(child), child))

        return frame


@total_ordering
class CommandId(object):

    def __init__(self, command):
        self.id = command

    def __lt__(self, other):
        return self.id < other.id

    def __eq__(self, other):
        return self.id == other.id

    __hash__ = None

    def __repr__(self):
        return 'ModuleCommand(id={})'.format(self.id)

    def to_command(self):
        return XPath.string(self.id)


def workflow_meta_from_session_datum(session_datum, next_datum):
    if isinstance(session_datum, SessionDatum):
        is_instance = isinstance(session_datum, InstanceDatum)
        return WorkflowDatumMeta(session_datum.id, session_datum.nodeset, session_datum.function, is_instance)
    if isinstance(session_datum, RemoteRequestQuery):
        return WorkflowQueryMeta(session_datum, next_datum)
    raise ValueError


@total_ordering
class WorkflowSessionMeta:
    """Base class for session datum metadata"""
    def __init__(self, datum_id):
        self.id = datum_id
        self._case_type = None
        # indicates whether this datum is here as a placeholder to match the parent module's datum
        self.from_parent_module = False

        self.source_id = self.id  # can be changed if the source datum has a different ID

    def __lt__(self, other):
        return self.id < other.id

    def __eq__(self, other):
        return self.id == other.id

    __hash__ = None

    @property
    def requires_selection(self):
        raise NotImplementedError

    @property
    def case_type(self):
        raise NotImplementedError

    def clone_to_match(self, source_id=None):
        raise NotImplementedError

    def to_stack_datum(self, is_endpoint=False):
        raise NotImplementedError


class WorkflowDatumMeta(WorkflowSessionMeta):
    """
    Class used in computing the form workflow. Allows comparison by SessionDatum.id and reference
    to SessionDatum.nodeset and SessionDatum.function attributes.
    """
    type_regex = re.compile(r"\[@case_type='([\w-]+)'\]")

    def __init__(self, datum_id, nodeset, function, is_instance):
        super().__init__(datum_id)

        self.nodeset = nodeset
        self.function = function
        self.is_instance = is_instance

    @property
    def requires_selection(self):
        return bool(self.nodeset)

    @property
    def case_type(self):
        """Get the case type from the nodeset or the function if possible
        """
        # Note that this does not support `additional_case_types`. If multiple case types are in use
        # then the case type will be inferred from the module case type.
        # See WorkflowHelper._add_missing_case_types
        def _extract_type(xpath):
            match = self.type_regex.search(xpath)
            return match.group(1) if match else None

        if not self._case_type:
            if self.nodeset:
                self._case_type = _extract_type(self.nodeset)
            elif self.function:
                self._case_type = _extract_type(self.function)

        return self._case_type

    @case_type.setter
    def case_type(self, case_type):
        if self.case_type and case_type != self.case_type:
            raise SuiteError("Datum already has a case type")
        self._case_type = case_type

    def clone_to_match(self, source_id=None):
        new_meta = WorkflowDatumMeta(self.id, self.nodeset, self.function, self.is_instance)
        new_meta.source_id = source_id or self.id
        return new_meta

    def to_stack_datum(self, is_endpoint=False):
        value = session_var(self.source_id) if self.requires_selection else self.function
        return StackDatum(id=self.id, value=value)

    def __repr__(self):
        return 'WorkflowDatumMeta(id={}, case_type={})'.format(self.id, self.case_type)


class WorkflowQueryMeta(WorkflowSessionMeta):
    """This class represents metadata about session query datums and is used
    for computing form workflows.
    """
    def __init__(self, query, next_datum):
        super().__init__(query.storage_instance)
        self.query = query
        self.next_datum = next_datum
        self.is_case_search = '/phone/search/' in self.query.url
        self.source_id = self.id
        if next_datum and self.is_case_search and isinstance(next_datum, WorkflowDatumMeta):
            # set source_id to the id of the next datum since that's what we'll use
            # to build the query
            self.source_id = self.next_datum.id

    @property
    def requires_selection(self):
        return not self.query.prompts and self.query.default_search

    @property
    def case_type(self):
        if not self._case_type:
            # This currently only assumes the first case type is the correct one.
            # The suite should be set up so that the first case type is the module's case type.
            type_data = [el for el in self.query.data if el.key == 'case_type']
            if type_data:
                self._case_type = type_data[0].ref.replace("'", "")  # TODO: what if this is dynamic

        return self._case_type

    @case_type.setter
    def case_type(self, case_type):
        if self.case_type and case_type != self.case_type:
            raise SuiteError("Datum already has a case type")
        self._case_type = case_type

    def clone_to_match(self, source_id=None):
        new_meta = WorkflowQueryMeta(self.query, self.next_datum)
        new_meta.source_id = source_id or self.id
        return new_meta

    def to_stack_datum(self, is_endpoint=False):
        wanted = (CASE_SEARCH_REGISTRY_ID_KEY, "case_type", "case_id")
        keys = {el.key for el in self.query.data}
        data = [QueryData(key=el.key, ref=el.ref) for el in self.query.data if el.key in wanted]
        if "case_id" not in keys and self.next_datum:
            if getattr(self.next_datum, "is_instance", False):
                data.append(QueryData(key="case_id", ref=".", nodeset=self._get_multi_select_nodeset()))
            else:
                ref_val = "$case_id" if is_endpoint else session_var(self.source_id)
                data.append(QueryData(key="case_id", ref=ref_val))
        url = self.query.url
        if self.is_case_search:
            # we don't need the full search results, just the case that's been selected
            url = url.replace('/phone/search/', '/phone/case_fixture/')
        return StackQuery(id=self.query.storage_instance, value=url, data=data)

    def _get_multi_select_nodeset(self):
        return SearchSelectedCasesInstanceXpath(self.source_id).instance()

    def __repr__(self):
        return (f"WorkflowQueryMeta("
                f"url={self.query.url}, "
                f"instance_id={self.query.storage_instance}, "
                f"source_id={self.source_id}"
                ")")


session_var_regex = re.compile(r"instance\('commcaresession'\)/session/data/(\w+)")


def _replace_session_references_in_stack(stack_children, current_session=None):
    """Given a list of stack children (commands and datums)
    replace any references in the datum to session variables that
    have already been added to the session.

    e.g.
    <datum id="case_id_a" value="instance('commcaresession')/session/data/case_id_new_a"/>
    <datum id="case_id_b" value="instance('commcaresession')/session/data/case_id_a"/>
                                                                          ^^^^^^^^^
    In the second datum replace ``case_id_a`` with ``case_id_new_a``.

    We have to do this because stack create blocks do not update the session after each datum
    is added so items put into the session in one step aren't available to later steps.
    """
    current_session_vars = [datum.id for datum in current_session] if current_session else []
    clean_children = []
    child_map = {}
    for child in stack_children:
        if isinstance(child, StackQuery):
            for data in child.data:
                session_vars = session_var_regex.findall(data.ref)
                for var in session_vars:
                    if var in child_map and var not in current_session_vars:
                        data.ref = data.ref.replace(session_var(var), child_map[var])
            clean_children.append(child)
        elif isinstance(child, StackDatum):
            session_vars = session_var_regex.findall(child.value)
            new_value = child.value
            for var in session_vars:
                if var in child_map and var not in current_session_vars:
                    new_value = new_value.replace(session_var(var), child_map[var])

            child_map[child.id] = new_value
            clean_children.append(StackDatum(id=child.id, value=new_value))
        else:
            clean_children.append(child)

    return clean_children
