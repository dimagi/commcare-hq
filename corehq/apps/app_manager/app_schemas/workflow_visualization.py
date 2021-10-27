from contextlib import contextmanager
from io import BytesIO

import attr
import graphviz

from corehq.apps.app_manager import id_strings
from corehq.apps.app_manager.const import (
    WORKFLOW_ROOT,
    WORKFLOW_PARENT_MODULE,
    WORKFLOW_MODULE,
    WORKFLOW_FORM, WORKFLOW_PREVIOUS,
)
from corehq.apps.app_manager.suite_xml.generator import SuiteGenerator
from corehq.apps.app_manager.suite_xml.post_process.workflow import WorkflowHelper, CommandId, \
    prepend_parent_frame_children
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
    attrs = attr.ib(default={})


class AppWorkflowVisualizer:
    ROOT = "root"
    START = "start"

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

    def add_form_menu_item(self, unique_id, name, parent_id):
        self.stack_append(Node(unique_id, name, parent_id))

    def add_form_entry(self, unique_id, name, parent_id):
        self.stack_append(Node(f"{unique_id}_form_entry", name, parent_id, attrs={"shape": "box"}))

    def add_case_list(self, node_id, case_type, has_search, parents=None):
        # TODO: make parents compulsory
        parent_id = node_id if not parents else None
        self.global_nodes.append(Node(
            node_id, f"Select '{case_type}' case", parent_id, attrs={"shape": "folder"}
        ))
        if has_search:
            self.edges.append(Edge(node_id, node_id, "Search"))
        for parent in (parents or []):
            self.edges.append(Edge(parent, node_id))
        return node_id

    def add_eof_workflow(self, form_id, target_node, label=None):
        self.edges.append(Edge(f"{form_id}_form_entry", target_node, label, attrs={"color": "grey"}))

    def add_eof_form_link(self, tail_form_id, head_form_id, label=None):
        self.edges.append(Edge(
            f"{tail_form_id}_form_entry", f"{head_form_id}_form_entry", label, attrs={"color": "grey"}
        ))

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
                        prevs = tuple([i.id for i in stack[:index + 1]])
                        item_id = f"{'.'.join(prevs)}"
                        if item_id not in added:
                            added.append(item_id)
                            if item.from_parent_module:
                                current_module = app.get_module_by_unique_id(module.root_module_id)
                                has_search = module_offers_search(current_module)
                            else:
                                has_search = module_offers_search(module)
                            workflow.add_case_list(item_id, item.case_type, has_search, parents=[previous])
                        id_stack.append(item_id)

            form_id = id_strings.form_command(form, module)
            with workflow.next_stack_level(len(commands) + 1):
                workflow.add_form_entry(form_id, trans(form.name), id_stack[-1])

            def _add_eof_workflow(workflow_option, condition=None):
                # TODO: label = _substitute_hashtags(app, form, condition or "")
                # frame_children
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
                if form.post_form_workflow_fallback:
                    conditions = [link.xpath for link in form.form_links if link.xpath.strip()]
                    if conditions:
                        no_conditions_match = ' and '.join(f'not({condition})' for condition in conditions)
                        _add_eof_workflow(form.post_form_workflow_fallback, no_conditions_match)

        if hasattr(module, 'case_list') and module.case_list.show:
            case_list_id = id_strings.case_list_command(module)
            workflow.add_module(case_list_id, f"{trans(module.name)} Case List")
            workflow.add_case_list(f"case_list_id.case_id", module.case_type, False, parents=[case_list_id])

    return workflow.render(app.name)


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
