from io import BytesIO

import graphviz

from corehq.apps.app_manager.const import (
    WORKFLOW_ROOT,
    WORKFLOW_PARENT_MODULE,
    WORKFLOW_MODULE,
    WORKFLOW_FORM,
)
from corehq.apps.app_manager.templatetags.xforms_extras import trans

WORKFLOW_DIAGRAM_NAME = "workflow_diagram.png"


def generate_app_workflow_diagram(app):
    source = generate_app_workflow_diagram_source(app)
    path = graphviz.Source(source).render(filename=f"{app.get_id}_workflow", format="png")
    with open(path, 'rb') as f:
        content = f.read()
        app.put_attachment(content, name=WORKFLOW_DIAGRAM_NAME, content_type="image/png")
        return BytesIO(content)


def generate_app_workflow_diagram_source(app):
    graph = graphviz.Digraph(
        app.name,
        graph_attr={"rankdir": "LR"},
    )

    graph.node("root", label="Home")
    graph.node("start", label="Start")
    graph.edge("root", "start")
    child_modules = []
    with graph.subgraph() as mods:
        mods.attr(rank="same")
        for module in app.get_modules():
            if module.root_module_id:
                child_modules.append(module)
            else:
                mods.node(module.get_or_create_unique_id(), trans(module.name))
                graph.edge("start", module.get_or_create_unique_id())

    for module in child_modules:
        graph.node(module.get_or_create_unique_id(), trans(module.name))
        graph.edge(module.root_module_id, module.get_or_create_unique_id())

    eof_nav = []
    model_form_edges = []
    with graph.subgraph() as forms:
        forms.attr(rank="same")
        for form in app.get_forms():
            module = form.get_module()
            forms.node(form.get_unique_id(), trans(form.name), shape="box")
            model_form_edges.append((module.get_or_create_unique_id(), form.get_unique_id()))

            if form.post_form_workflow == WORKFLOW_ROOT:
                eof_nav.append((form.get_unique_id(), "start", None))
            if form.post_form_workflow == WORKFLOW_PARENT_MODULE:
                try:
                    module.root_module
                except ModuleNotFoundError:
                    pass
                else:
                    eof_nav.append((form.get_unique_id(), module.root_module_id, None))
            if form.post_form_workflow == WORKFLOW_MODULE:
                eof_nav.append((form.get_unique_id(), module.get_or_create_unique_id(), None))
            # TODO
            # if form.post_form_workflow == WORKFLOW_PREVIOUS:
            #     graph.edge(form.get_unique_id(), module.get_or_create_unique_id())
            if form.post_form_workflow == WORKFLOW_FORM:
                eof_nav.extend([(form.get_unique_id(), link.form_id, link.xpath) for link in form.form_links])

    graph.edges(model_form_edges)

    for tail, head, label in eof_nav:
        graph.edge(tail, head, label=label, style="dotted")
    return graph.source
