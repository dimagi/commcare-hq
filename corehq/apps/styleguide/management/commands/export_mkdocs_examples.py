# management/commands/export_examples_html.py
import os
from dataclasses import dataclass
from pathlib import Path
from typing import List

from django.conf import settings
from django.core.management.base import BaseCommand
from django.template.loader import render_to_string

from corehq.apps.hqwebapp.utils.bootstrap import set_bootstrap_version5
from corehq.apps.styleguide.context import (
    CrispyFormsDemo,
    CrispyFormsWithJsDemo,
    HtmlWithJsDemo,
    get_example_context,
    get_html_example_context,
    get_js_example_context,
    get_python_example_context,
)
from corehq.apps.styleguide.examples.bootstrap5.multiselect_form import (
    MultiselectDemoForm,
)
from corehq.apps.styleguide.examples.bootstrap5.select2_ajax_form import (
    Select2AjaxDemoForm,
)
from corehq.apps.styleguide.examples.bootstrap5.select2_autocomplete_ko_form import (
    Select2AutocompleteKoForm,
)
from corehq.apps.styleguide.examples.bootstrap5.select2_css_class_form import (
    Select2CssClassDemoForm,
)
from corehq.apps.styleguide.examples.bootstrap5.select2_dynamic_ko_form import (
    Select2DynamicKoForm,
)
from corehq.apps.styleguide.examples.bootstrap5.select2_manual_form import (
    Select2ManualDemoForm,
)
from corehq.apps.styleguide.examples.bootstrap5.select2_static_ko_form import (
    Select2StaticKoForm,
)
from corehq.apps.styleguide.examples.bootstrap5.select_toggle_form import (
    SelectToggleDemoForm,
)


@dataclass
class Example:
    name: str
    content: str
    using: str
    language: str = 'html'

@dataclass
class Page:
    name: str
    template: str
    examples: List[Example]


examples = {
    'toggles': get_example_context('styleguide/bootstrap5/examples/toggles.html'),
    'toggles_crispy': CrispyFormsDemo(
        SelectToggleDemoForm(), get_python_example_context('select_toggle_form.py'),
    ),
    'select2_manual': HtmlWithJsDemo(
        code_html=get_html_example_context('select2_manual.html'),
        code_js=get_js_example_context('select2_manual.js'),
    ),
    'select2_manual_allow_clear': HtmlWithJsDemo(
        code_html=get_html_example_context('select2_manual_allow_clear.html'),
        code_js=get_js_example_context('select2_manual_allow_clear.js'),
    ),
    'select2_manual_crispy': CrispyFormsWithJsDemo(
        form=Select2ManualDemoForm(),
        code_python=get_python_example_context('select2_manual_form.py'),
        code_js=get_js_example_context('select2_manual_crispy.js'),
    ),
    'select2_css_class': get_example_context('styleguide/bootstrap5/examples/select2_css_class.html'),
    'select2_css_class_multiple': get_example_context(
        'styleguide/bootstrap5/examples/select2_css_class_multiple.html'),
    'select2_css_class_crispy': CrispyFormsDemo(
        Select2CssClassDemoForm(), get_python_example_context('select2_css_class_form.py'),
    ),
    'select2_ko_dynamic': HtmlWithJsDemo(
        code_html=get_html_example_context('select2_ko_dynamic.html'),
        code_js=get_js_example_context('select2_ko_dynamic.js'),
    ),
    'select2_ko_dynamic_crispy': CrispyFormsWithJsDemo(
        form=Select2DynamicKoForm(),
        code_python=get_python_example_context('select2_dynamic_ko_form.py'),
        code_js=get_js_example_context('select2_dynamic_ko_crispy.js'),
    ),
    'select2_ko_static': HtmlWithJsDemo(
        code_html=get_html_example_context('select2_ko_static.html'),
        code_js=get_js_example_context('select2_ko_static.js'),
    ),
    'select2_ko_static_crispy': CrispyFormsWithJsDemo(
        form=Select2StaticKoForm(),
        code_python=get_python_example_context('select2_static_ko_form.py'),
        code_js=get_js_example_context('select2_static_ko_crispy.js'),
    ),
    'select2_ko_autocomplete': HtmlWithJsDemo(
        code_html=get_html_example_context('select2_ko_autocomplete.html'),
        code_js=get_js_example_context('select2_ko_autocomplete.js'),
    ),
    'select2_ko_autocomplete_crispy': CrispyFormsWithJsDemo(
        form=Select2AutocompleteKoForm(),
        code_python=get_python_example_context('select2_autocomplete_ko_form.py'),
        code_js=get_js_example_context('select2_autocomplete_ko_crispy.js'),
    ),
    'multiselect': HtmlWithJsDemo(
        code_html=get_html_example_context('multiselect.html'),
        code_js=get_js_example_context('multiselect.js'),
    ),
    'multiselect_crispy': CrispyFormsWithJsDemo(
        form=MultiselectDemoForm(),
        code_python=get_python_example_context('multiselect_form.py'),
        code_js=get_js_example_context('multiselect_crispy.js'),
    ),
    'select2_ajax_crispy': CrispyFormsDemo(
        Select2AjaxDemoForm(), get_python_example_context('select2_ajax_form.py'),
    ),
    # Tables examples
    'basic_table': get_example_context('styleguide/bootstrap5/examples/basic_table.html'),
    'sectioned_table': get_example_context('styleguide/bootstrap5/examples/sectioned_table.html'),
    'datatables': HtmlWithJsDemo(
        code_html=get_html_example_context('datatables.html'),
        code_js=get_js_example_context('datatables.js'),
    ),
    'paginated_table': HtmlWithJsDemo(
        code_html=get_html_example_context('paginated_table.html'),
        code_js=get_js_example_context('paginated_table.js'),
    ),
}

selections_page = Page(
    name="selections",
    template= 'styleguide/bootstrap5/mkdocs/selections.html',
    examples= [
        # Select-Toggle examples
        Example(name='toggles', content=examples['toggles'], using="styleguide/bootstrap5/code_example.html"),
        Example(
            name='toggles_crispy',
            content=examples['toggles_crispy'],
            using="styleguide/bootstrap5/form_example.html"
        ),
        # Select2 manual initialization examples
        Example(
            name='select2_manual',
            content=examples['select2_manual'],
            using="styleguide/bootstrap5/html_js_example.html"
        ),
        Example(name='select2_manual_allow_clear', content=examples['select2_manual_allow_clear'], using="styleguide/bootstrap5/html_js_example.html"),
        Example(name='select2_manual_crispy', content=examples['select2_manual_crispy'], using="styleguide/bootstrap5/form_js_example.html"),
        # Select2 with CSS class examples
        Example(name='select2_css_class', content=examples['select2_css_class'], using="styleguide/bootstrap5/code_example.html"),
        Example(name='select2_css_class_multiple', content=examples['select2_css_class_multiple'], using="styleguide/bootstrap5/code_example.html"),
        Example(name='select2_css_class_crispy', content=examples['select2_css_class_crispy'], using="styleguide/bootstrap5/form_example.html"),
        # Select2 with Knockout.js examples
        Example(name='select2_ko_dynamic', content=examples['select2_ko_dynamic'], using="styleguide/bootstrap5/html_js_example.html"),
        Example(name='select2_ko_dynamic_crispy', content=examples['select2_ko_dynamic_crispy'], using="styleguide/bootstrap5/form_js_example.html"),
        Example(name='select2_ko_static', content=examples['select2_ko_static'], using="styleguide/bootstrap5/html_js_example.html"),
        Example(name='select2_ko_static_crispy', content=examples['select2_ko_static_crispy'], using="styleguide/bootstrap5/form_js_example.html"),
        Example(name='select2_ko_autocomplete', content=examples['select2_ko_autocomplete'], using="styleguide/bootstrap5/html_js_example.html"),
        Example(name='select2_ko_autocomplete_crispy', content=examples['select2_ko_autocomplete_crispy'], using="styleguide/bootstrap5/form_js_example.html"),
        # Multiselect examples
        Example(name='multiselect', content=examples['multiselect'], using="styleguide/bootstrap5/html_js_example.html"),
        Example(name='multiselect_crispy', content=examples['multiselect_crispy'], using="styleguide/bootstrap5/form_js_example.html"),
        # Select2 with AJAX examples
        Example(name='select2_ajax_crispy', content=examples['select2_ajax_crispy'], using="styleguide/bootstrap5/form_example.html"),
    ]
)

tables_page = Page(
    name="tables",
    template='styleguide/bootstrap5/mkdocs/tables.html',
    examples=[
        # Basic table examples
        Example(name='basic_table', content=examples['basic_table'], using="styleguide/bootstrap5/code_example.html"),
        Example(name='sectioned_table', content=examples['sectioned_table'], using="styleguide/bootstrap5/code_example.html"),
        # Interactive table examples
        Example(name='datatables', content=examples['datatables'], using="styleguide/bootstrap5/html_js_example.html"),
        Example(name='paginated_table', content=examples['paginated_table'], using="styleguide/bootstrap5/html_js_example.html"),
    ]
)

all_pages = [
    selections_page,
    tables_page,
]


class Command(BaseCommand):
    name = "export_assets_html"
    help = "Export rendered examples and assets_head HTML for MkDocs"

    def handle(self, *args, **kwargs):
        set_bootstrap_version5()

        base_dir = Path(settings.BASE_DIR)
        print("base_dir:", base_dir)
        examples_dir = os.path.join(base_dir, "corehq/apps/styleguide/templates/styleguide/bootstrap5/examples")
        output_dir = base_dir / "docs" / "styleguide" / "examples" / "bootstrap5"
        output_dir.mkdir(parents=True, exist_ok=True)

        self.stdout.write(f"Rendering examples from {examples_dir} → {output_dir}")

        examples_output_dir = base_dir / "docs" / "styleguide" / "_includes" / "examples" / "bootstrap5"
        base_output_dir = base_dir / "docs" / "styleguide" / "_includes" / "bootstrap5"

        examples_output_dir.mkdir(parents=True, exist_ok=True)
        base_output_dir.mkdir(parents=True, exist_ok=True)

        for page in all_pages:
            self.stdout.write("Rendering page and examples for: " + page.name)
            # Render page content
            page_path = base_output_dir / f"{page.name}.html"
            rendered_page = render_to_string(
                page.template,
                context={
                    "csrf_token": "",
                    "LANGUAGE_CODE": "en",
                }
            )
            page_path.write_text(rendered_page, encoding="utf-8")
            # Render each example
            for example in page.examples:
                self.stdout.write("Rendering example: " + example.name)
                rendered_example = render_to_string(
                    example.using,
                    context={
                        "content": example.content,
                        "LANGUAGE_CODE": "en",
                    }
                )
                example_path = examples_output_dir / f"{example.name}.html"
                example_path.write_text(rendered_example, encoding="utf-8")

        self.stdout.write(self.style.SUCCESS("All pages and examples rendered successfully."))
