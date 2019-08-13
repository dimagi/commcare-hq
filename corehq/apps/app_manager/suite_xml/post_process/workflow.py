from __future__ import absolute_import
from __future__ import unicode_literals
from collections import defaultdict, namedtuple
from functools import total_ordering
from os.path import commonprefix
import re
from xml.sax.saxutils import unescape

from corehq.apps.app_manager import id_strings
from corehq.apps.app_manager.const import (
    RETURN_TO, )
from corehq.apps.app_manager.exceptions import SuiteValidationError
from corehq.apps.app_manager.suite_xml.contributors import PostProcessor
from corehq.apps.app_manager.suite_xml.xml_models import StackDatum, Stack, CreateFrame
from corehq.apps.app_manager.xpath import CaseIDXPath, session_var, \
    XPath
from memoized import memoized
from six.moves import filter


class WorkflowHelper(PostProcessor):

    def __init__(self, suite, app, modules):
        super(WorkflowHelper, self).__init__(suite, app, modules)

    @property
    @memoized
    def root_module_datums(self):
        root_modules = [module for module in self.modules if module.put_in_root]
        return [
            datum for module in root_modules
            for datum in self.get_module_datums('m{}'.format(module.id)).values()
        ]

    def update_suite(self):
        """
        Add stack elements to form entry elements to configure app workflow. This updates
        the Entry objects in place.
        """
        for module in self.modules:
            for form in module.get_suite_forms():
                form_command = id_strings.form_command(form, module)
                stack_frames = []
                end_of_form_frames = EndOfFormNavigationWorkflow(self).form_workflow_frames(module, form)
                if end_of_form_frames:
                    stack_frames.extend(end_of_form_frames)
                else:
                    stack_frames.extend(CaseListFormWorkflow(self).case_list_forms_frames(form))

                self.create_workflow_stack(form_command, stack_frames)

    def get_frame_children(self, command, target_module, module_only=False, include_target_root=False):
        """
        For a form return the list of stack frame children that are required
        to navigate to that form.

        Given command may be a form (mX-fY) or case list menu item (mX-case-list).

        This is based on the following algorithm:

        * Add the module the form is in to the stack (we'll call this `m`)
        * Walk through all forms in the module, determine what datum selections
          are present in all of the forms (this may be an empty set)
          * Basically if there are three forms that respectively load
            * f1: v1, v2, v3, v4
            * f2: v1, v2, v4
            * f3: v1, v2
          * The longest common chain is v1, v2
        * Add a datum for each of those values to the stack
        * Add the form "command id" for the <entry> to the stack
        * Add the remainder of the datums for the current form to the stack
        * For the three forms above, the stack entries for "last element" would be
          * m, v1, v2, f1, v3, v4
          * m, v1, v2, f2, v4
          * m, v1, v2, f3

        :returns:   list of strings and DatumMeta objects. String represent stack commands
                    and DatumMeta's represent stack datums.
        """
        match = re.search(r'^(m\d+)-(.*)', command)
        if not match:
            raise Exception("Unrecognized command: {}".format(command))
        target_module_id = match.group(1)
        target_form_id = match.group(2)

        frame_children = []

        def _add_new_datums(datums):
            frame_children.extend([d for d in datums if d not in frame_children])

        # Determine datums needed for target form
        module_datums = self.get_module_datums(target_module_id)
        form_datums = module_datums[target_form_id]

        target_module_command = None
        root_module_command = None
        root_datums = [[]]

        module_command = id_strings.menu_id(target_module)
        if module_command == id_strings.ROOT:
            target_module_datums = self.root_module_datums
        else:
            target_module_command = CommandId(module_command)
            target_module_datums = list(module_datums.values())  # [ [datums for f0], [datums for f1], ...]
            root_module = target_module.root_module
            if root_module and include_target_root:
                # Module has a parent. Store the parent's needed datums and command.
                root_datums = list(self.get_module_datums(id_strings.menu_id(root_module)).values())
                root_module_command = id_strings.menu_id(target_module.root_module)
                if root_module_command != id_strings.ROOT:
                    root_module_command = CommandId(root_module_command)

        # First add parent module, if any: datums needed by all of its forms, then menu command
        _add_new_datums(commonprefix(root_datums))
        if root_module_command:
            frame_children.append(root_module_command)

        # Then add target module: datums needed by all of its forms, then menu command
        _add_new_datums(commonprefix(target_module_datums))
        if target_module_command:
            frame_children.append(target_module_command)

        # Then add form itself and any additional datums it needs
        if not module_only:
            frame_children.append(CommandId(command))
            _add_new_datums(form_datums)

        return frame_children

    def create_workflow_stack(self, form_command, frame_metas):
        frames = [_f for _f in [meta.to_frame() for meta in frame_metas if meta is not None] if _f]
        if not frames:
            return

        entry = self.get_form_entry(form_command)
        if not entry.stack:
            entry.stack = Stack()

        for frame in frames:
            entry.stack.add_frame(frame)

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

    def get_form_entry(self, form_command):
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
            module_id, form_id = command.split('-', 1)
            entries[command] = e
            if not e.datums:
                datums[module_id][form_id] = []
            else:
                for d in e.datums:
                    datums[module_id][form_id].append(WorkflowDatumMeta.from_session_datum(d))

        for module_id, form_datum_map in datums.items():
            for form_id, entry_datums in form_datum_map.items():
                self._add_missing_case_types(module_id, form_id, entry_datums)

        return entries, datums

    @memoized
    def _form_datums(self, module_id, form_id):
        module_id = module_id[1:]  # string 'm'
        form_id = form_id[1:]  # strip 'f'
        module = self.app.get_module(module_id)
        if module.module_type == 'shadow':
            module = module.source_module

        if not module:
            return {}
        form = module.get_form(form_id)
        if not form:
            return {}
        return {d.datum.id: d for d in self.entries_helper.get_datums_meta_for_form_generic(form, module)}

    def _add_missing_case_types(self, module_id, form_id, entry_datums):
        form_datums_by_id = self._form_datums(module_id, form_id)
        for entry_datum in entry_datums:
            if not entry_datum.case_type:
                form_datum = form_datums_by_id.get(entry_datum.id)
                if form_datum:
                    entry_datum.case_type = form_datum.case_type
                    entry_datum.from_parent_module = form_datum.from_parent

    @staticmethod
    def get_datums_matched_to_source(target_frame_elements, source_datums):
        """
        Attempt to match the target session variables with ones in the source session.
        Making some large assumptions about how people will actually use this feature
        """
        unused_source_datums = list(source_datums)
        for target_datum in target_frame_elements:
            if not isinstance(target_datum, WorkflowDatumMeta) or not target_datum.requires_selection:
                yield target_datum
            else:
                match = WorkflowHelper.find_best_match(target_datum, unused_source_datums)
                if match:
                    unused_source_datums = [datum for datum in unused_source_datums if datum.id != match.id]

                yield match if match else target_datum

    @staticmethod
    def find_best_match(target_datum, source_datums):
        """Find the datum in the list of source datums that best matches the target datum (if any)
        """
        candidate = None
        for source_datum in source_datums:
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
        from corehq.apps.app_manager.const import (
            WORKFLOW_PREVIOUS, WORKFLOW_MODULE, WORKFLOW_ROOT, WORKFLOW_FORM, WORKFLOW_PARENT_MODULE
        )

        def frame_children_for_module(module_, include_user_selections=True):
            frame_children = []
            if module_.root_module:
                frame_children.extend(frame_children_for_module(module_.root_module))

            if include_user_selections:
                this_module_children = self.helper.get_frame_children(id_strings.form_command(module_.get_form(0)),
                                                                      module_, module_only=True)
                for child in this_module_children:
                    if child not in frame_children:
                        frame_children.append(child)
            else:
                module_command = id_strings.menu_id(module_)
                if module_command != id_strings.ROOT:
                    frame_children.append(CommandId(module_command))

            return frame_children

        def _get_static_stack_frame(form_workflow, xpath=None):
            if form_workflow == WORKFLOW_ROOT:
                return StackFrameMeta(xpath, [], allow_empty_frame=True)
            elif form_workflow == WORKFLOW_MODULE:
                frame_children = frame_children_for_module(module, include_user_selections=False)
                return StackFrameMeta(xpath, frame_children)
            elif form_workflow == WORKFLOW_PARENT_MODULE:
                root_module = module.root_module
                frame_children = frame_children_for_module(root_module)
                return StackFrameMeta(xpath, frame_children)
            elif form_workflow == WORKFLOW_PREVIOUS:
                frame_children = self.helper.get_frame_children(id_strings.form_command(form),
                                                                module, include_target_root=True)

                # since we want to go the 'previous' screen we need to drop the last
                # datum
                last = frame_children.pop()
                while isinstance(last, WorkflowDatumMeta) and not last.requires_selection:
                    # keep removing last element until we hit a command
                    # or a non-autoselect datum
                    last = frame_children.pop()

                return StackFrameMeta(xpath, frame_children)

        stack_frames = []

        if form.post_form_workflow == WORKFLOW_FORM:
            source_form_datums = self.helper.get_form_datums(form)

            for link in form.form_links:
                target_form = self.helper.app.get_form(link.form_id)
                target_module = target_form.get_module()

                target_frame_children = self.helper.get_frame_children(id_strings.form_command(target_form),
                                                                       target_module)
                if link.datums:
                    frame_children = EndOfFormNavigationWorkflow.get_datums_matched_to_manual_values(
                        target_frame_children, link.datums, form
                    )
                else:
                    frame_children = WorkflowHelper.get_datums_matched_to_source(
                        target_frame_children, source_form_datums
                    )

                if target_module in module.get_child_modules():
                    parent_frame_children = self.helper.get_frame_children(
                        id_strings.form_command(module.get_form(0)), module, module_only=True)

                    # exclude frame children from the child module if they are already
                    # supplied by the parent module
                    parent_ids = {parent.id for parent in parent_frame_children}
                    frame_children = parent_frame_children + [
                        child for child in frame_children
                        if child.id not in parent_ids
                    ]

                stack_frames.append(StackFrameMeta(link.xpath, frame_children, current_session=source_form_datums))
            if form.post_form_workflow_fallback:
                # for the fallback negative all if conditions/xpath expressions and use that as the xpath for this
                link_xpaths = [link.xpath for link in form.form_links]
                # remove any empty string
                link_xpaths = [x for x in link_xpaths if x.strip()]
                if link_xpaths:
                    negate_of_all_link_paths = (
                        ' and '.join(
                            ['not(' + link_xpath + ')' for link_xpath in link_xpaths]
                        )
                    )
                    static_stack_frame_for_fallback = _get_static_stack_frame(
                        form.post_form_workflow_fallback,
                        negate_of_all_link_paths
                    )
                    if static_stack_frame_for_fallback:
                        stack_frames.append(static_stack_frame_for_fallback)
        else:
            static_stack_frame = _get_static_stack_frame(form.post_form_workflow)
            if static_stack_frame:
                stack_frames.append(static_stack_frame)
        return stack_frames

    @staticmethod
    def get_datums_matched_to_manual_values(target_frame_elements, manual_values, form):
        """
        Attempt to match the target session variables with ones that the user
        has entered manually
        """
        manual_values_by_name = {datum.name: datum.xpath for datum in manual_values}
        for child in target_frame_elements:
            if not isinstance(child, WorkflowDatumMeta) or not child.requires_selection:
                yield child
            else:
                manual_value = manual_values_by_name.get(child.id)
                if manual_value:
                    yield StackDatum(id=child.id, value=manual_value)
                else:
                    raise SuiteValidationError("Unable to link form '{}', missing variable '{}'".format(
                        form.default_name(), child.id
                    ))


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
        command = None
        if len(target_module.forms):
            command = id_strings.form_command(target_module.get_form(0))
        elif target_module.case_list and target_module.case_list.show:
            command = id_strings.case_list_command(target_module)

        if command:
            target_frame_children = self.helper.get_frame_children(command, target_module, module_only=True)
            remaining_target_frame_children = [fc for fc in target_frame_children if fc.id not in ids_on_stack]
            frame_children = WorkflowHelper.get_datums_matched_to_source(
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
            # OR it could mean that not all the forms in the target module have the same case management configuration.
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
        if isinstance(child, WorkflowDatumMeta):
            child = child.to_stack_datum()
        self.children.append(child)

    def to_frame(self):
        if not self.children and not self.allow_empty_frame:
            return

        children = _replace_session_references_in_stack(self.children, current_session=self.current_session)

        frame = CreateFrame(if_clause=self.if_clause)

        for child in children:
            if isinstance(child, CommandId):
                frame.add_command(XPath.string(child.id))
            elif isinstance(child, StackDatum):
                frame.add_datum(child)
            else:
                raise Exception("Unexpected child type: {} ({})".format(type(child), child))

        return frame


@total_ordering
class CommandId(object):

    def __init__(self, command):
        self.id = command

    def __lt__(self, other):
        return self.id < other.id

    def __eq__(self, other):
        return self.id == other.id

    def __ne__(self, other):
        return not self == other

    __hash__ = None

    def __repr__(self):
        return 'ModuleCommand(id={})'.format(self.id)


@total_ordering
class WorkflowDatumMeta(object):
    """
    Class used in computing the form workflow. Allows comparison by SessionDatum.id and reference
    to SessionDatum.nodeset and SessionDatum.function attributes.
    """
    type_regex = re.compile(r"\[@case_type='([\w-]+)'\]")

    def __init__(self, datum_id, nodeset, function):
        self.id = datum_id
        self.nodeset = nodeset
        self.function = function
        self._case_type = None
        # indicates whether this datum is here as a placeholder to match the parent module's datum
        self.from_parent_module = False

        self.source_id = self.id  # can be changed if the source datum has a different ID

    @classmethod
    def from_session_datum(cls, session_datum):
        return cls(session_datum.id, session_datum.nodeset, session_datum.function)

    @property
    def requires_selection(self):
        return bool(self.nodeset)

    @property
    def case_type(self):
        """Get the case type from the nodeset or the function if possible
        """
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
            raise Exception("Datum already has a case type")
        self._case_type = case_type

    def clone_to_match(self, source_id=None):
        new_meta = WorkflowDatumMeta(self.id, self.nodeset, self.function)
        new_meta.source_id = source_id or self.id
        return new_meta

    def to_stack_datum(self):
        value = session_var(self.source_id) if self.requires_selection else self.function
        return StackDatum(id=self.id, value=value)

    def __lt__(self, other):
        return self.id < other.id

    def __eq__(self, other):
        return self.id == other.id

    def __ne__(self, other):
        return not self == other

    __hash__ = None

    def __repr__(self):
        return 'WorkflowDatumMeta(id={}, case_type={})'.format(self.id, self.case_type)


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
        if not isinstance(child, StackDatum):
            clean_children.append(child)
            continue
        session_vars = session_var_regex.findall(child.value)
        new_value = child.value
        for var in session_vars:
            if var in child_map and var not in current_session_vars:
                new_value = new_value.replace(session_var(var), child_map[var])

        child_map[child.id] = new_value
        clean_children.append(StackDatum(id=child.id, value=new_value))

    return clean_children
