from __future__ import absolute_import
from collections import defaultdict
from functools import total_ordering
from os.path import commonprefix
import re
from xml.sax.saxutils import unescape

from corehq.apps.app_manager import id_strings
from corehq.apps.app_manager.const import (
    RETURN_TO, )
from corehq.apps.app_manager.exceptions import SuiteError
from corehq.apps.app_manager.suite_xml.contributors import PostProcessor
from corehq.apps.app_manager.suite_xml.xml_models import StackDatum, Stack, CreateFrame
from corehq.apps.app_manager.xpath import CaseIDXPath, session_var, \
    XPath
from dimagi.utils.decorators.memoized import memoized


class WorkflowHelper(PostProcessor):
    def __init__(self, suite, app, modules):
        super(WorkflowHelper, self).__init__(suite, app, modules)

        root_modules = [module for module in self.modules if getattr(module, 'put_in_root', False)]
        self.root_module_datums = [datum for module in root_modules
                          for datum in self.get_module_datums(u'm{}'.format(module.id)).values()]

    def update_suite(self):
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
        for module in self.modules:
            for form in module.get_forms():
                form_command = id_strings.form_command(form)
                if_prefix = None
                stack_frames = []
                case_list_form_frames = self.case_list_forms_frames(form)
                stack_frames.extend(case_list_form_frames)

                if case_list_form_frames:
                    if_prefix = session_var(RETURN_TO).count().eq(0)

                stack_frames.extend(self.form_workflow_frames(if_prefix, module, form))

                self.create_workflow_stack(form_command, stack_frames)

    def case_list_forms_frames(self, form):
        stack_frames = []
        if form.is_registration_form() and form.is_case_list_form:
            for target_module in form.case_list_modules:

                return_to = session_var(RETURN_TO)
                target_command = id_strings.menu_id(target_module)

                def get_if_clause(case_count_xpath):
                    return XPath.and_(
                        return_to.count().eq(1),
                        return_to.eq(XPath.string(target_command)),
                        case_count_xpath
                    )

                if form.form_type == 'module_form':
                    [reg_action] = form.get_registration_actions(target_module.case_type)
                    source_session_var = form.session_var_for_action(reg_action)
                if form.form_type == 'advanced_form':
                    # match case session variable
                    reg_action = form.get_registration_actions(target_module.case_type)[0]
                    source_session_var = reg_action.case_session_var

                source_case_id = session_var(source_session_var)
                case_count = CaseIDXPath(source_case_id).case().count()

                frame_case_created = StackFrameMeta(None, get_if_clause(case_count.gt(0)))
                stack_frames.append(frame_case_created)

                frame_case_not_created = StackFrameMeta(None, get_if_clause(case_count.eq(0)))
                stack_frames.append(frame_case_not_created)

                def get_case_type_created_by_form(form):
                    if form.form_type == 'module_form':
                        [reg_action] = form.get_registration_actions(target_module.case_type)
                        if reg_action == 'open_case':
                            return form.get_module().case_type
                        else:
                            return reg_action.case_type
                    elif form.form_type == 'advanced_form':
                        return form.get_registration_actions(target_module.case_type)[0].case_type

                def add_datums_for_target(module, source_form_dm, allow_missing=False):
                    """
                    Given a target module and a list of datums from the source module add children
                    to the stack frames that are required to by the target module and present in the source datums
                    list.
                    """
                    # assume all forms in the module have the same datums
                    target_form_dm = self.get_form_datums(module.get_form(0))

                    def get_target_dm(case_type):
                        try:
                            [target_dm] = [
                                target_meta for target_meta in target_form_dm
                                if target_meta.case_type == case_type
                            ]
                        except ValueError:
                            raise SuiteError(
                                "Return module for case list form has mismatching datums: {}".format(form.unique_id)
                            )

                        return target_dm

                    used = set()
                    for source_meta in source_form_dm:
                        if source_meta.case_type:
                            # This is true for registration forms where the case being created is a subcase
                            try:
                                target_dm = get_target_dm(source_meta.case_type)
                            except SuiteError:
                                if source_meta.requires_selection:
                                    raise
                            else:
                                used.add(source_meta)
                                meta = WorkflowDatumMeta.from_session_datum(source_meta)
                                frame_case_created.add_child(meta.to_stack_datum(datum_id=target_dm.id))
                                frame_case_not_created.add_child(meta.to_stack_datum(datum_id=target_dm.id))
                        else:
                            source_case_type = get_case_type_created_by_form(form)
                            try:
                                target_dm = get_target_dm(source_case_type)
                            except SuiteError:
                                if not allow_missing:
                                    raise
                            else:
                                used.add(source_meta)
                                datum_meta = WorkflowDatumMeta.from_session_datum(target_dm)
                                frame_case_created.add_child(datum_meta.to_stack_datum(source_id=source_meta.id))

                    # return any source datums that were not already added to the target
                    return [dm for dm in source_form_dm if dm not in used]

                source_form_dm = self.get_form_datums(form)

                if target_module.root_module_id:
                    # add stack children for the root module before adding any for the child module.
                    root_module = target_module.root_module
                    root_module_command = CommandId(id_strings.menu_id(root_module))
                    frame_case_created.add_child(root_module_command)
                    frame_case_not_created.add_child(root_module_command)

                    source_form_dm = add_datums_for_target(root_module, source_form_dm, allow_missing=True)

                frame_case_created.add_child(CommandId(target_command))
                frame_case_not_created.add_child(CommandId(target_command))
                add_datums_for_target(target_module, source_form_dm)

        return stack_frames

    def form_workflow_frames(self, if_prefix, module, form):
        from corehq.apps.app_manager.models import (
            WORKFLOW_PREVIOUS, WORKFLOW_MODULE, WORKFLOW_ROOT, WORKFLOW_FORM, WORKFLOW_PARENT_MODULE
        )

        def frame_children_for_module(module_, include_user_selections=True):
            frame_children = []
            if module_.root_module:
                frame_children.extend(frame_children_for_module(module_.root_module))

            if include_user_selections:
                this_module_children = self.get_frame_children(module_.get_form(0), module_only=True)
                for child in this_module_children:
                    if child not in frame_children:
                        frame_children.append(child)
            else:
                module_command = id_strings.menu_id(module_)
                if module_command != id_strings.ROOT:
                    frame_children.append(CommandId(module_command))

            return frame_children

        stack_frames = []
        if form.post_form_workflow == WORKFLOW_ROOT:
            stack_frames.append(StackFrameMeta(if_prefix, None, [], allow_empty_frame=True))
        elif form.post_form_workflow == WORKFLOW_MODULE:
            frame_children = frame_children_for_module(module, include_user_selections=False)
            stack_frames.append(StackFrameMeta(if_prefix, None, frame_children))
        elif form.post_form_workflow == WORKFLOW_PARENT_MODULE:
            root_module = module.root_module
            frame_children = frame_children_for_module(root_module)
            stack_frames.append(StackFrameMeta(if_prefix, None, frame_children))
        elif form.post_form_workflow == WORKFLOW_PREVIOUS:
            frame_children = self.get_frame_children(form)

            # since we want to go the 'previous' screen we need to drop the last
            # datum
            last = frame_children.pop()
            while isinstance(last, WorkflowDatumMeta) and not last.requires_selection:
                # keep removing last element until we hit a command
                # or a non-autoselect datum
                last = frame_children.pop()

            stack_frames.append(StackFrameMeta(if_prefix, None, frame_children))
        elif form.post_form_workflow == WORKFLOW_FORM:
            source_form_datums = self.get_form_datums(form)
            for link in form.form_links:
                target_form = self.app.get_form(link.form_id)
                target_module = target_form.get_module()

                target_frame_children = self.get_frame_children(target_form)
                if link.datums:
                    frame_children = WorkflowHelper.get_datums_matched_to_manual_values(
                        target_frame_children, link.datums
                    )
                else:
                    frame_children = WorkflowHelper.get_datums_matched_to_source(
                        target_frame_children, source_form_datums
                    )

                if target_module in module.get_child_modules():
                    parent_frame_children = self.get_frame_children(module.get_form(0), module_only=True)

                    # exclude frame children from the child module if they are already
                    # supplied by the parent module
                    parent_ids = {parent.id for parent in parent_frame_children}
                    frame_children = parent_frame_children + [
                        child for child in frame_children
                        if child.id not in parent_ids
                    ]

                stack_frames.append(StackFrameMeta(if_prefix, link.xpath, frame_children))

        return stack_frames

    @staticmethod
    def get_datums_matched_to_source(target_frame_elements, source_datums):
        """
        Attempt to match the target session variables with ones in the source session.
        Making some large assumptions about how people will actually use this feature
        """
        datum_index = -1
        for child in target_frame_elements:
            if not isinstance(child, WorkflowDatumMeta) or not child.requires_selection:
                yield child
            else:
                datum_index += 1
                try:
                    source_datum = source_datums[datum_index]
                except IndexError:
                    yield child.to_stack_datum()
                else:
                    if child.id != source_datum.id and not source_datum.case_type or \
                            source_datum.case_type == child.case_type:
                        yield child.to_stack_datum(source_id=source_datum.id)
                    else:
                        yield child.to_stack_datum()

    @staticmethod
    def get_datums_matched_to_manual_values(target_frame_elements, manual_values):
        """
        Attempt to match the target session variables with ones that the user
        has entered manually
        """
        manual_values_by_name = {datum.name: datum.xpath for datum in manual_values}
        for child in target_frame_elements:
            if not isinstance(child, WorkflowDatumMeta) or not child.requires_selection:
                yield child
            else:
                manual_values = manual_values_by_name.get(child.id)
                if manual_values:
                    yield StackDatum(id=child.id, value=manual_values)
                else:
                    raise SuiteError("Unable to link forms, missing form variable: {}".format(
                        child.id
                    ))

    def get_frame_children(self, target_form, module_only=False):
        """
        For a form return the list of stack frame children that are required
        to navigate to that form.

        This is based on the following algorithm:

        * Add the module the form is in to the stack (we'll call this `m`)
        * Walk through all forms in the module, determine what datum selections are present in all of the modules
          (this may be an empty set)
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
        target_form_command = id_strings.form_command(target_form)
        target_module_id, target_form_id = target_form_command.split('-')
        module_command = id_strings.menu_id(target_form.get_module())
        module_datums = self.get_module_datums(target_module_id)
        form_datums = module_datums[target_form_id]

        if module_command == id_strings.ROOT:
            datums_list = self.root_module_datums
        else:
            datums_list = module_datums.values()  # [ [datums for f0], [datums for f1], ...]

        common_datums = commonprefix(datums_list)
        remaining_datums = form_datums[len(common_datums):]

        frame_children = [CommandId(module_command)] if module_command != id_strings.ROOT else []
        frame_children.extend(common_datums)
        if not module_only:
            frame_children.append(CommandId(target_form_command))
            frame_children.extend(remaining_datums)

        return frame_children

    def create_workflow_stack(self, form_command, frame_metas):
        frames = filter(None, [meta.to_frame() for meta in frame_metas])
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

        return entries, datums


class StackFrameMeta(object):
    """
    Class used in computing the form workflow.
    """
    def __init__(self, if_prefix, if_clause, children=None, allow_empty_frame=False):
        if if_prefix:
            template = '({{}}) and ({})'.format(if_clause) if if_clause else '{}'
            if_clause = template.format(if_prefix)
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

        frame = CreateFrame(if_clause=self.if_clause)

        for child in self.children:
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

    def __repr__(self):
        return 'ModuleCommand(id={})'.format(self.id)


@total_ordering
class WorkflowDatumMeta(object):
    """
    Class used in computing the form workflow. Allows comparison by SessionDatum.id and reference
    to SessionDatum.nodeset and SessionDatum.function attributes.
    """
    type_regex = re.compile("\[@case_type='([\w-]+)'\]")

    def __init__(self, datum_id, nodeset, function):
        self.id = datum_id
        self.nodeset = nodeset
        self.function = function

    @classmethod
    def from_session_datum(cls, session_datum):
        return cls(session_datum.id, session_datum.nodeset, session_datum.function)

    @property
    def requires_selection(self):
        return bool(self.nodeset)

    @property
    @memoized
    def case_type(self):
        """Get the case type from the nodeset or the function if possible
        """
        def _extract_type(xpath):
            match = self.type_regex.search(xpath)
            return match.group(1) if match else None

        if self.nodeset:
            return _extract_type(self.nodeset)
        elif self.function:
            return _extract_type(self.function)

    def to_stack_datum(self, datum_id=None, source_id=None):
        value = session_var(source_id or self.id) if self.requires_selection else self.function
        return StackDatum(id=datum_id or self.id, value=value)

    def __lt__(self, other):
        return self.id < other.id

    def __eq__(self, other):
        return self.id == other.id

    def __ne__(self, other):
        return not self == other

    def __repr__(self):
        return 'DatumMeta(id={}, case_type={})'.format(self.id, self.case_type)
