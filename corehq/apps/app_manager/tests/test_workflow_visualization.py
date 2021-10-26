import inspect

import graphviz
from testil import eq

from corehq.apps.app_manager.app_schemas.workflow_visualization import generate_app_workflow_diagram_source
from corehq.apps.app_manager.const import (
    WORKFLOW_FORM,
    WORKFLOW_ROOT,
    WORKFLOW_MODULE,
    WORKFLOW_PREVIOUS
)
from corehq.apps.app_manager.models import FormLink
from corehq.apps.app_manager.tests.app_factory import AppFactory


def test_workflow_diagram_child_module_form_links():
    factory = AppFactory(build_version='2.9.0')
    m0, m0f0 = factory.new_basic_module('enroll child', 'child')
    factory.form_opens_case(m0f0)

    m1, m1f0 = factory.new_basic_module('child visit', 'child')
    factory.form_requires_case(m1f0)
    factory.form_opens_case(m1f0, case_type='visit', is_subcase=True)

    m2, m2f0 = factory.new_advanced_module('visit history', 'visit', parent_module=m1)
    factory.form_requires_case(m2f0, 'child')
    factory.form_requires_case(m2f0, 'visit', parent_case_type='child')

    m0f0.post_form_workflow = WORKFLOW_FORM
    m0f0.form_links = [
        FormLink(xpath="true()", form_id=m1f0.unique_id),
    ]

    m1f0.post_form_workflow = WORKFLOW_FORM
    m1f0.form_links = [
        FormLink(xpath="(today() - dob) &lt; 7", form_id=m2f0.unique_id),
    ]
    source = generate_app_workflow_diagram_source(factory.app)
    eq(_normalize(source), inspect.cleandoc("""
    digraph "Untitled Application" {
        graph [rankdir=LR]
        root [label=Home]
        start [label=Start]
        root -> start
        start -> "enroll child_module"
        start -> "child visit_module"
        {
            rank=same
            "enroll child_module" [label="enroll child module [en] "]
            "child visit_module" [label="child visit module [en] "]
        }
        "visit history_module" [label="visit history module [en] "]
        "child visit_module" -> "visit history_module"
        {
            rank=same
            "enroll child_form_0" [label="enroll child form 0 [en] " shape=box]
            "child visit_form_0" [label="child visit form 0 [en] " shape=box]
            "visit history_form_0" [label="visit history form 0 [en] " shape=box]
        }
        "enroll child_module" -> "enroll child_form_0"
        "child visit_module" -> "child visit_form_0"
        "visit history_module" -> "visit history_form_0"
        "enroll child_form_0" -> "child visit_form_0" [label="true()" style=dotted]
        "child visit_form_0" -> "visit history_form_0" [label="(today() - dob) &lt; 7" style=dotted]
    }
    """))


def test_workflow_diagram_post_form_workflow_root():
    app = _build_workflow_app(WORKFLOW_ROOT)
    source = generate_app_workflow_diagram_source(app)
    eq(_normalize(source), inspect.cleandoc("""
    digraph "Untitled Application" {
        graph [rankdir=LR]
        root [label=Home]
        start [label=Start]
        root -> start
        start -> m0_module
        {
            rank=same
            m0_module [label="m0 module [en] "]
        }
        m1_module [label="m1 module [en] "]
        m0_module -> m1_module
        {
            rank=same
            m0_form_0 [label="m0 form 0 [en] " shape=box]
            m1_form_0 [label="m1 form 0 [en] " shape=box]
        }
        m0_module -> m0_form_0
        m1_module -> m1_form_0
        m0_form_0 -> start [style=dotted]
        m1_form_0 -> start [style=dotted]
    }
    """))


def test_workflow_diagram_post_form_workflow_module():
    app = _build_workflow_app(WORKFLOW_MODULE)
    source = generate_app_workflow_diagram_source(app)
    eq(_normalize(source), inspect.cleandoc("""
    digraph "Untitled Application" {
        graph [rankdir=LR]
        root [label=Home]
        start [label=Start]
        root -> start
        start -> m0_module
        {
            rank=same
            m0_module [label="m0 module [en] "]
        }
        m1_module [label="m1 module [en] "]
        m0_module -> m1_module
        {
            rank=same
            m0_form_0 [label="m0 form 0 [en] " shape=box]
            m1_form_0 [label="m1 form 0 [en] " shape=box]
        }
        m0_module -> m0_form_0
        m1_module -> m1_form_0
        m0_form_0 -> m0_module [style=dotted]
        m1_form_0 -> m1_module [style=dotted]
    }
    """))


def test_workflow_diagram_post_form_workflow_parent():
    app = _build_workflow_app(WORKFLOW_PREVIOUS)
    source = generate_app_workflow_diagram_source(app)
    # TODO
    graphviz.Source(source).render(view=True)


def _build_workflow_app(mode):
    factory = AppFactory(build_version='2.9.0')
    m0, m0f0 = factory.new_basic_module('m0', '')
    factory.new_basic_module('m1', 'patient', parent_module=m0)

    for module in factory.app.get_modules():
        for form in module.get_forms():
            form.post_form_workflow = mode

    return factory.app


def _normalize(source):
    return source.replace("\t", "    ")
