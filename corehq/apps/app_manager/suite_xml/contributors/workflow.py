from collections import defaultdict
import copy
from functools import total_ordering
import re
from os.path import commonprefix
from xml.sax.saxutils import unescape
from corehq.apps.app_manager import id_strings
from corehq.apps.app_manager.const import RETURN_TO
from corehq.apps.app_manager.suite_xml.basic import SuiteContributor
from corehq.apps.app_manager.suite_xml.xml import CreateFrame, StackDatum, Stack
from corehq.apps.app_manager.xpath import session_var, XPath
from dimagi.utils.decorators.memoized import memoized


@total_ordering
class DatumMeta(object):
    """
    Class used in computing the form workflow. Allows comparison by SessionDatum.id and reference
    to SessionDatum.nodeset and SessionDatum.function attributes.
    """
    type_regex = re.compile("\[@case_type='([\w_]+)'\]")

    def __init__(self, session_datum):
        self.id = session_datum.id
        self.nodeset = session_datum.nodeset
        self.function = session_datum.function
        self.source_id = self.id

    @property
    @memoized
    def case_type(self):
        if not self.nodeset:
            return None

        match = self.type_regex.search(self.nodeset)
        return match.group(1)

    def __lt__(self, other):
        return self.id < other.id

    def __eq__(self, other):
        return self.id == other.id

    def __ne__(self, other):
        return not self == other

    def __repr__(self):
        return 'DatumMeta(id={}, case_type={}, source_id={})'.format(self.id, self.case_type, self.source_id)


class WorkflowHelper(object):
    def __init__(self, suite, app, modules):
        self.suite = suite
        self.app = app
        self.modules = modules

        root_modules = [module for module in self.modules if getattr(module, 'put_in_root', False)]
        self.root_module_datums = [datum for module in root_modules
                          for datum in self.get_module_datums(u'm{}'.format(module.id)).values()]

    def add_form_workflow(self):
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
        from corehq.apps.app_manager.models import (
            WORKFLOW_DEFAULT, WORKFLOW_PREVIOUS, WORKFLOW_MODULE, WORKFLOW_ROOT, WORKFLOW_FORM
        )

        for module in self.modules:
            for form in module.get_forms():
                if form.post_form_workflow == WORKFLOW_DEFAULT:
                    continue

                form_command = id_strings.form_command(form)

                if form.post_form_workflow == WORKFLOW_ROOT:
                    self.create_workflow_stack(form_command, [], True)
                elif form.post_form_workflow == WORKFLOW_MODULE:
                    module_command = id_strings.menu_id(module)
                    frame_children = [module_command] if module_command != id_strings.ROOT else []
                    self.create_workflow_stack(form_command, frame_children)
                elif form.post_form_workflow == WORKFLOW_PREVIOUS:
                    frame_children = self.get_frame_children(form)

                    # since we want to go the 'previous' screen we need to drop the last
                    # datum
                    last = frame_children.pop()
                    while isinstance(last, DatumMeta) and last.function:
                        # keep removing last element until we hit a command
                        # or a non-autoselect datum
                        last = frame_children.pop()

                    self.create_workflow_stack(form_command, frame_children)
                elif form.post_form_workflow == WORKFLOW_FORM:
                    module_id, form_id = form_command.split('-')
                    source_form_datums = self.get_form_datums(module_id, form_id)
                    for link in form.form_links:
                        target_form = self.app.get_form(link.form_id)
                        target_module = target_form.get_module()

                        frame_children = self.get_frame_children(target_form)
                        frame_children = WorkflowHelper.get_datums_matched_to_source(frame_children, source_form_datums)

                        if target_module in module.get_child_modules():
                            parent_frame_children = self.get_frame_children(module.get_form(0), module_only=True)

                            # exclude frame children from the child module if they are already
                            # supplied by the parent module
                            child_ids_in_parent = {getattr(child, "id", child) for child in parent_frame_children}
                            frame_children = parent_frame_children + [
                                child for child in frame_children
                                if getattr(child, "id", child) not in child_ids_in_parent
                            ]

                        self.create_workflow_stack(form_command, frame_children, if_clause=link.xpath)

    @staticmethod
    def get_datums_matched_to_source(target_frame_elements, source_datums):
        """
        Attempt to match the target session variables with ones in the source session.
        Making some large assumptions about how people will actually use this feature
        """
        datum_index = -1
        for child in target_frame_elements:
            if not isinstance(child, DatumMeta) or child.function:
                yield child
            else:
                datum_index += 1
                try:
                    source_datum = source_datums[datum_index]
                except IndexError:
                    yield child
                else:
                    if child.id != source_datum.id and not source_datum.case_type or \
                            source_datum.case_type == child.case_type:
                        target_datum = copy.copy(child)
                        target_datum.source_id = source_datum.id
                        yield target_datum
                    else:
                        yield child

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

        frame_children = [module_command] if module_command != id_strings.ROOT else []
        frame_children.extend(common_datums)
        if not module_only:
            frame_children.append(target_form_command)
            frame_children.extend(remaining_datums)

        return frame_children

    def create_workflow_stack(self, form_command, frame_children,
                              allow_empty_stack=False, if_clause=None):
        if not frame_children and not allow_empty_stack:
            return

        entry, is_new = self._get_entry(form_command)
        entry = self.get_form_entry(form_command)
        if not is_new:
            # TODO: find a more general way of handling multiple contributions to the workflow
            if_prefix = '{} = 0'.format(session_var(RETURN_TO).count())
            template = '({{}}) and ({})'.format(if_clause) if if_clause else '{}'
            if_clause = template.format(if_prefix)

        if_clause = unescape(if_clause) if if_clause else None
        frame = CreateFrame(if_clause=if_clause)
        entry.stack.add_frame(frame)

        for child in frame_children:
            if isinstance(child, basestring):
                frame.add_command(XPath.string(child))
            else:
                value = session_var(child.source_id) if child.nodeset else child.function
                frame.add_datum(StackDatum(id=child.id, value=value))
        return frame

    @memoized
    def _get_entry(self, form_command):
        entry = self.get_form_entry(form_command)
        if not entry.stack:
            entry.stack = Stack()
            return entry, True
        else:
            return entry, False

    def get_form_datums(self, module_id, form_id):
        return self.get_module_datums(module_id)[form_id]

    def get_module_datums(self, module_id):
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
                    datums[module_id][form_id].append(DatumMeta(d))

        return entries, datums


class WorkflowContributor(SuiteContributor):
    def contribute(self):
        if self.app.enable_post_form_workflow:
            WorkflowHelper(self.suite, self.app, self.modules).add_form_workflow()
