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
from corehq.apps.app_manager.suite_xml.post_process.workflow import (
    WorkflowHelper, CommandId, CaseListFormWorkflow
)
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


@attr.s
class DefaultStyle:
    module_shape = "box3d"
    form_menu_shape = "ellipse"
    form_entry_shape = "box"
    case_list_shape = "folder"
    eof_color = "#0066CC"
    case_list_form_color = "#663399"


class AppWorkflowVisualizer:
    ROOT = "root"
    START = "start"

    def __init__(self, styles=None):
        self.global_nodes = []
        self.node_stack = []
        self.edges = []
        self.pos = 0
        self.fill_stack()
        self.styles = styles or DefaultStyle

        self.module_attrs = {"shape": self.styles.module_shape}
        self.form_menu_attrs = {"shape": self.styles.form_menu_shape}
        self.form_entry_attrs = {"shape": self.styles.form_entry_shape}
        self.case_list_attrs = {"shape": self.styles.case_list_shape}
        self.eof_attrs = {"color": self.styles.eof_color, "constraint": "false"}
        self.form_link_attrs = {"color": self.styles.eof_color}
        self.case_list_form_link_attrs = {"color": self.styles.case_list_form_color, "constraint": "false"}

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
        self.stack_append(Node(unique_id, name, parent_id or self.START, attrs=self.module_attrs))

    def add_form_menu_item(self, unique_id, name, parent_id=None):
        self.stack_append(Node(unique_id, name, parent_id or self.START, attrs=self.form_menu_attrs))

    def add_form_entry(self, unique_id, name, parent_id):
        self.stack_append(Node(f"{unique_id}_form_entry", name, parent_id, attrs=self.form_entry_attrs))

    def add_case_list(self, node_id, case_type, has_search, parent):
        self.global_nodes.append(Node(
            node_id, f"Select '{case_type}' case", attrs=self.case_list_attrs
        ))
        self.add_edge(Edge(parent, node_id))
        if has_search:
            self.add_edge(Edge(node_id, node_id, "Search"))
        return node_id

    def add_eof_workflow(self, form_id, target_node, label=None):
        self.add_edge(Edge(f"{form_id}_form_entry", target_node, label, attrs=self.eof_attrs))

    def add_eof_form_link(self, tail_form_id, head_form_id, label=None):
        self.add_edge(Edge(
            f"{tail_form_id}_form_entry", f"{head_form_id}_form_entry", label, attrs=self.form_link_attrs
        ))

    def add_case_list_form_link(self, tail_id, form_id, label):
        self.add_edge(Edge(
            tail_id, f"{form_id}_form_entry", label, attrs=self.case_list_form_link_attrs
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
            root_graph.edge(edge.tail, edge.head, label=edge.label or None, **edge.attrs)
        return root_graph.source


def generate_app_workflow_diagram_source(app, style=None):
    generator = SuiteGenerator(app)
    generator.generate_suite()
    suite = generator.suite

    workflow = AppWorkflowVisualizer(style)
    helper = WorkflowHelper(suite, app, list(app.get_modules()))
    added = []
    for module in app.get_modules():
        for form in module.get_suite_forms():
            frame_children = helper.get_frame_children_for_navigation(form.get_module(), form)

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

            form_has_eof = add_eof_edges(app, module, form, workflow, id_stack)
            if not form_has_eof:
                add_case_list_form_eof_edges(module, form, helper, workflow)

        if hasattr(module, 'case_list') and module.case_list.show:
            case_list_id = id_strings.case_list_command(module)
            workflow.add_module(case_list_id, f"{trans(module.name)} Case List")
            workflow.add_case_list(f"{case_list_id}.case_id", module.case_type, False, case_list_id)

    return workflow.render(app.name)


def add_eof_edges(app, module, form, graph, id_stack, workflow_option=None, label=None):
    form_id = id_strings.form_command(form, module)

    workflow_option = workflow_option or form.post_form_workflow
    label = _substitute_hashtags(app, form, label or "")
    # frame_children
    if workflow_option == WORKFLOW_ROOT:
        graph.add_eof_workflow(form_id, "start", label)
        return True

    if workflow_option == WORKFLOW_PARENT_MODULE:
        try:
            module.root_module
        except ModuleNotFoundError:
            return False
        else:
            module_command = id_strings.menu_id(app.get_module_by_unique_id(module.root_module_id))
            graph.add_eof_workflow(form_id, module_command, label)
            return True

    if workflow_option == WORKFLOW_MODULE:
        graph.add_eof_workflow(form_id, id_strings.menu_id(module), label)
        return True

    if workflow_option == WORKFLOW_PREVIOUS and len(id_stack) > 1:
        graph.add_eof_workflow(form_id, id_stack[-2], label)
        return True

    if form.post_form_workflow == WORKFLOW_FORM:
        for link in form.form_links:
            label = _substitute_hashtags(app, form, link.xpath)
            to_form = app.get_form(link.form_id)
            to_id = id_strings.form_command(to_form, to_form.get_module())
            graph.add_eof_form_link(form_id, to_id, label)
        if form.post_form_workflow_fallback:
            conditions = [link.xpath for link in form.form_links if link.xpath.strip()]
            if conditions:
                no_conditions_match = ' and '.join(f'not({condition})' for condition in conditions)
                add_eof_edges(
                    app, module, form, graph, id_stack,
                    workflow_option=form.post_form_workflow_fallback,
                    label=no_conditions_match
                )
        return True


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
        xpath = CaseIDXPath(session_var(datum_meta.datum.id)).case()
        hashtag = "#case"
        if datum_meta.case_type:
            hashtag = f"{hashtag}:{datum_meta.case_type}"
        hashtags[xpath] = hashtag

    for xpath, hashtag in hashtags.items():
        xpath_expression = xpath_expression.replace(xpath, hashtag)
    return xpath_expression
