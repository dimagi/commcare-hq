import re
from contextlib import contextmanager
from io import BytesIO

import attr
import graphviz

from corehq.apps.app_manager import id_strings
from corehq.apps.app_manager.const import (
    WORKFLOW_ROOT,
    WORKFLOW_PARENT_MODULE,
    WORKFLOW_MODULE,
    WORKFLOW_FORM,
    WORKFLOW_PREVIOUS,
)
from corehq.apps.app_manager.suite_xml.generator import SuiteGenerator
from corehq.apps.app_manager.suite_xml.post_process.workflow import WorkflowHelper, CommandId, \
    prepend_parent_frame_children, CaseListFormWorkflow
from corehq.apps.app_manager.suite_xml.sections.details import DetailContributor
from corehq.apps.app_manager.suite_xml.sections.entries import EntriesHelper
from corehq.apps.app_manager.templatetags.xforms_extras import trans
from corehq.apps.app_manager.util import module_offers_search
from corehq.apps.app_manager.xpath import UsercaseXPath, CaseIDXPath, session_var

WORKFLOW_DIAGRAM_NAME = "workflow_diagram.png"


def generate_app_workflow_diagram(app):
    source = generate_app_workflow_diagram_source(app)
    path = graphviz.Source(source).render(filename=f"{app.get_id}_workflow", format="png")
    with open(path, 'rb') as f:
        content = f.read()
        app.put_attachment(content, name=WORKFLOW_DIAGRAM_NAME, content_type="image/png")
        return BytesIO(content)


@attr.s
class Node:
    id = attr.ib()
    label = attr.ib()
    parent = attr.ib(default=None)
    attrs = attr.ib(default={})


@attr.s
class Edge:
    tail = attr.ib()
    head = attr.ib()
    label = attr.ib(default=None)
    attrs = attr.ib(default={}, cmp=False)


class AppWorkflowVisualizer:
    ROOT = "root"
    START = "start"
    WORKFLOW_STYLE = {"color": "grey", "constraint": "false"}
    FORM_LINK_STYLE = {"color": "grey"}

    def __init__(self):
        self.global_nodes = []
        self.node_stack = []
        self.edges = []
        self.pos = 0
        self.fill_stack()

    def stack_append(self, node):
        """Append node to the current stack frame"""
        self.node_stack[self.pos].append(node)

    def fill_stack(self):
        """Fill the stack up to the given position (or the current position)"""
        if len(self.node_stack) <= self.pos + 1:
            self.node_stack.append([])

    @contextmanager
    def next_stack_level(self, levels_to_move=1):
        """Context manager to advance the stack level by the given number"""
        self.pos += levels_to_move
        self.fill_stack()
        yield
        self.pos -= levels_to_move

    def add_module(self, unique_id, name, parent_id=None):
        self.stack_append(Node(unique_id, name, parent_id or self.START))

    def add_form_menu_item(self, unique_id, name, parent_id=None):
        self.stack_append(Node(unique_id, name, parent_id or self.START))

    def add_form_entry(self, unique_id, name, parent_id):
        self.stack_append(Node(f"{unique_id}_form_entry", name, parent_id, attrs={"shape": "box"}))

    def add_case_list(self, node_id, case_type, has_search, parent):
        self.global_nodes.append(Node(
            node_id, f"Select '{case_type}' case", attrs={"shape": "folder"}
        ))
        self.add_edge(Edge(parent, node_id))
        if has_search:
            self.add_edge(Edge(node_id, node_id, "Search"))
        return node_id

    def add_eof_workflow(self, form_id, target_node, label=None):
        self.add_edge(Edge(f"{form_id}_form_entry", target_node, label, attrs=self.WORKFLOW_STYLE))

    def add_eof_form_link(self, tail_form_id, head_form_id, label=None):
        self.add_edge(Edge(
            f"{tail_form_id}_form_entry", f"{head_form_id}_form_entry", label, attrs=self.FORM_LINK_STYLE
        ))

    def add_case_list_form_link(self, tail_id, form_id, label):
        self.add_edge(Edge(
            tail_id, f"{form_id}_form_entry", label, attrs=self.WORKFLOW_STYLE
        ))

    def add_edge(self, edge):
        if edge not in self.edges:
            self.edges.append(edge)

    def render(self, name):
        root_graph = graphviz.Digraph(
            name,
            graph_attr={"rankdir": "LR"},
        )

        def _add_node(graph, node):
            graph.node(node.id, node.label, **node.attrs)
            if node.parent:
                root_graph.edge(node.parent, node.id)

        _add_node(root_graph, Node(self.ROOT, "Root"))
        _add_node(root_graph, Node(self.START, "Start", parent=self.ROOT))

        for pos, nodes in enumerate(self.node_stack):
            if not nodes:
                continue

            with root_graph.subgraph() as sub:
                sub.attr(rank="same")
                for node in nodes:
                    _add_node(sub, node)

        for node in self.global_nodes:
            _add_node(root_graph, node)

        for edge in self.edges:
            root_graph.edge(edge.tail, edge.head, label=edge.label, **edge.attrs)
        return root_graph.source


def generate_app_workflow_diagram_source(app):
    generator = SuiteGenerator(app)
    generator.generate_suite()
    suite = generator.suite

    workflow = AppWorkflowVisualizer()
    helper = WorkflowHelper(suite, app, list(app.get_modules()))
    added = []
    for module in app.get_modules():
        for form in module.get_suite_forms():
            frame_children = helper.get_frame_children(form.get_module(), form)
            if form.get_module().root_module_id:
                root_module = helper.app.get_module_by_unique_id(form.get_module().root_module_id)
                frame_children = prepend_parent_frame_children(helper, frame_children, root_module)

            stack = [d for d in frame_children if getattr(d, "requires_selection", True)]
            id_stack = []
            commands = []
            for index, item in enumerate(stack):
                previous = id_stack[-1] if id_stack else None
                with workflow.next_stack_level(len(commands)):
                    if isinstance(item, CommandId):
                        if item.id not in added:
                            added.append(item.id)
                            if '-f' in item.id:
                                m_id, f_id = item.id.split("-")
                                module = app.get_module(int(m_id[1:]))
                                form = module.get_form(int(f_id[1:]))
                                workflow.add_form_menu_item(item.id, trans(form.name), previous)
                            else:
                                module = app.get_module(int(item.id[1:]))
                                workflow.add_module(item.id, trans(module.name), previous)
                        id_stack.append(item.id)
                        commands.append(item)
                    else:
                        module_commands = [c.id for c in commands if '-f' not in c.id]
                        item_id = f"{'.'.join(module_commands + [item.id])}"
                        if item_id not in added:
                            added.append(item_id)
                            if item.from_parent_module:
                                current_module = app.get_module_by_unique_id(module.root_module_id)
                            else:
                                current_module = module
                            has_search = module_offers_search(current_module)
                            workflow.add_case_list(item_id, item.case_type, has_search, previous)
                            add_case_list_form_edge(item_id, app, current_module, workflow)
                        else:
                            workflow.add_edge(Edge(previous, item_id))
                        id_stack.append(item_id)

            form_id = id_strings.form_command(form, module)
            with workflow.next_stack_level(len(commands) + 1):
                workflow.add_form_entry(form_id, trans(form.name), id_stack[-1])

            form_has_eof = False
            def _add_eof_workflow(workflow_option, condition=None):
                # TODO: label = _substitute_hashtags(app, form, condition or "")
                # frame_children
                form_has_eof = True
                label = condition
                if workflow_option == WORKFLOW_ROOT:
                    workflow.add_eof_workflow(form_id, "start", label)
                if workflow_option == WORKFLOW_PARENT_MODULE:
                    try:
                        module.root_module
                    except ModuleNotFoundError:
                        pass
                    else:
                        module_command = id_strings.menu_id(app.get_module_by_unique_id(module.root_module_id))
                        workflow.add_eof_workflow(form_id, module_command, label)
                if workflow_option == WORKFLOW_MODULE:
                    workflow.add_eof_workflow(form_id, id_strings.menu_id(module), label)
                if workflow_option == WORKFLOW_PREVIOUS:
                    workflow.add_eof_workflow(form_id, id_stack[-2], label)

            _add_eof_workflow(form.post_form_workflow)

            if form.post_form_workflow == WORKFLOW_FORM:
                for link in form.form_links:
                    # label = _substitute_hashtags(app, form, link.xpath)
                    to_form = app.get_form(link.form_id)
                    to_id = id_strings.form_command(to_form, to_form.get_module())
                    workflow.add_eof_form_link(form_id, to_id, link.xpath)
                    form_has_eof = True
                if form.post_form_workflow_fallback:
                    conditions = [link.xpath for link in form.form_links if link.xpath.strip()]
                    if conditions:
                        no_conditions_match = ' and '.join(f'not({condition})' for condition in conditions)
                        _add_eof_workflow(form.post_form_workflow_fallback, no_conditions_match)

            if not form_has_eof:
                add_case_list_form_eof_edges(module, form, helper, workflow)

        if hasattr(module, 'case_list') and module.case_list.show:
            case_list_id = id_strings.case_list_command(module)
            workflow.add_module(case_list_id, f"{trans(module.name)} Case List")
            workflow.add_case_list(f"{case_list_id}.case_id", module.case_type, False, case_list_id)

    return workflow.render(app.name)


def add_case_list_form_eof_edges(module, form, workflow_helper, graph):
    form_id = id_strings.form_command(form, module)
    for frame in CaseListFormWorkflow(workflow_helper).case_list_forms_frames(form):
        if not frame.children:
            continue

        label = None
        if frame.if_clause:
            case_xpath = r".*count\(instance\('casedb'\)/casedb/case\[.*\]\)"
            if re.match(f"{case_xpath} > 0", frame.if_clause):
                label = "Case Created"
            elif re.match(f"{case_xpath} = 0", frame.if_clause):
                label = "Case Not Created"
            else:
                label = frame.if_clause

        if isinstance(frame.children[-1], CommandId):
            graph.add_eof_workflow(form_id, frame.children[-1].id, label)
        else:
            ids = [d.id for d in frame.children]
            graph.add_eof_workflow(form_id, f"{'.'.join(ids)}", label)


def add_case_list_form_edge(item_id, app, module, graph):
    if module.case_list_form.form_id:
        case_list_form = app.get_form(module.case_list_form.form_id)
        if DetailContributor.form_is_valid_for_case_list_action(app, case_list_form, module):
            form_id = id_strings.form_command(case_list_form, case_list_form.get_module())
            graph.add_case_list_form_link(item_id, form_id, trans(module.case_list_form.label))


def _substitute_hashtags(app, form, xpath_expression):
    """Replace xpath expressions with simpler hashtag expressions"""
    hashtags = {
        UsercaseXPath().case(): "#user",
    }
    for datum_meta in EntriesHelper(app).get_datums_meta_for_form_generic(form):
        if datum_meta.requires_selection and datum_meta.case_type and not datum_meta.is_new_case_id:
            xpath = CaseIDXPath(session_var(datum_meta.datum.id)).case()
            hashtag = "#parent_case" if datum_meta.from_parent else "#case"
            hashtags[xpath] = hashtag

    for xpath, hashtag in hashtags.items():
        xpath_expression = xpath_expression.replace(xpath, hashtag)
    return xpath_expression
