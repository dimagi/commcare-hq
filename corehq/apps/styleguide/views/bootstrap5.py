from django.shortcuts import render

from corehq.apps.hqwebapp.decorators import use_bootstrap5
from corehq.apps.styleguide.context import (
    get_navigation_context,
    get_interaction_colors,
    get_neutral_colors,
    get_common_icons,
    get_custom_icons,
    get_example_context,
    get_python_example_context,
    CrispyFormsDemo,
    CrispyFormsWithJsDemo,
    get_html_example_context,
    get_js_example_context,
    get_gradient_colors,
    CodeForDisplay,
    CodeForDisplayWithPartial,
    HtmlWithJsDemo,
)
from corehq.apps.styleguide.examples.bootstrap5.checkbox_form import CheckboxDemoForm
from corehq.apps.styleguide.examples.bootstrap5.crispy_forms_basic import BasicCrispyExampleForm
from corehq.apps.styleguide.examples.bootstrap5.crispy_forms_errors import ErrorsCrispyExampleForm
from corehq.apps.styleguide.examples.bootstrap5.crispy_forms_knockout import KnockoutCrispyExampleForm
from corehq.apps.styleguide.examples.bootstrap5.crispy_forms_knockout_validation import \
    KnockoutValidationCrispyExampleForm
from corehq.apps.styleguide.examples.bootstrap5.disabled_fields import DisabledFieldsExampleForm
from corehq.apps.styleguide.examples.bootstrap5.multiselect_form import MultiselectDemoForm
from corehq.apps.styleguide.examples.bootstrap5.placeholder_help_text import PlaceholderHelpTextExampleForm
from corehq.apps.styleguide.examples.bootstrap5.select2_ajax_form import Select2AjaxDemoForm
from corehq.apps.styleguide.examples.bootstrap5.select2_autocomplete_ko_form import Select2AutocompleteKoForm
from corehq.apps.styleguide.examples.bootstrap5.select2_css_class_form import Select2CssClassDemoForm
from corehq.apps.styleguide.examples.bootstrap5.select2_dynamic_ko_form import Select2DynamicKoForm
from corehq.apps.styleguide.examples.bootstrap5.select2_manual_form import Select2ManualDemoForm
from corehq.apps.styleguide.examples.bootstrap5.select2_static_ko_form import Select2StaticKoForm
from corehq.apps.styleguide.examples.bootstrap5.select_toggle_form import SelectToggleDemoForm
from corehq.apps.styleguide.examples.bootstrap5.switch_form import SwitchDemoForm


@use_bootstrap5
def styleguide_home(request):
    return render(request, 'styleguide/bootstrap5/home.html', get_navigation_context("styleguide_home_b5"))


@use_bootstrap5
def styleguide_code_guidelines(request):
    return render(request, 'styleguide/bootstrap5/code_guidelines.html',
                  get_navigation_context("styleguide_code_guidelines_b5"))


@use_bootstrap5
def styleguide_migration_guide(request):
    return render(request, 'styleguide/bootstrap5/migration_guide.html',
                  get_navigation_context("styleguide_migration_guide_b5"))


@use_bootstrap5
def styleguide_javascript_guide(request):
    return render(request, 'styleguide/bootstrap5/javascript_guide.html',
                  get_navigation_context("styleguide_javascript_guide_b5"))


@use_bootstrap5
def styleguide_html_guide(request):
    context = get_navigation_context("styleguide_html_guide_b5")
    context.update({
        "examples": {
            'indentation': CodeForDisplay(
                code=get_example_context('styleguide/bootstrap5/examples/html_guide/indentation.html'),
                language="Django",
            ),
            'block_and_inline': CodeForDisplay(
                code=get_example_context('styleguide/bootstrap5/examples/html_guide/block_and_inline.html'),
                language="Django",
            ),
            'standard_attributes': CodeForDisplay(
                code=get_example_context('styleguide/bootstrap5/examples/html_guide/standard_attributes.html'),
                language="Django",
            ),
            'attribute_js': CodeForDisplay(
                code=get_example_context('styleguide/bootstrap5/examples/html_guide/attribute_js.html'),
                language="Django",
            ),
            'attribute_json': CodeForDisplay(
                code=get_example_context('styleguide/bootstrap5/examples/html_guide/attribute_json.html'),
                language="Django",
            ),
            'attribute_no_wrap': CodeForDisplay(
                code=get_example_context('styleguide/bootstrap5/examples/html_guide/attribute_no_wrap.html'),
                language="Django",
            ),
            'attribute_wrap_data': CodeForDisplay(
                code=get_example_context('styleguide/bootstrap5/examples/html_guide/attribute_wrap_data.html'),
                language="Django",
            ),
            'attribute_wrap_length': CodeForDisplay(
                code=get_example_context('styleguide/bootstrap5/examples/html_guide/attribute_wrap_length.html'),
                language="Django",
            ),
            'self_closing': CodeForDisplay(
                code=get_example_context('styleguide/bootstrap5/examples/html_guide/self_closing.html'),
                language="Django",
            ),
            'self_closing_line': CodeForDisplay(
                code=get_example_context('styleguide/bootstrap5/examples/html_guide/self_closing_line.html'),
                language="Django",
            ),
            'final_example': CodeForDisplay(
                code=get_example_context('styleguide/bootstrap5/examples/html_guide/final_example.html'),
                language="Django",
            ),
        },
    })
    return render(request, 'styleguide/bootstrap5/html_guide.html', context)


@use_bootstrap5
def styleguide_htmx_and_alpine(request):
    context = get_navigation_context("styleguide_htmx_and_alpine_b5")
    context.update({
        "examples": {
            'htmx_get_started': CodeForDisplay(
                code=get_example_context('styleguide/bootstrap5/examples/htmx_get_started.html'),
                language="Django",
            ),
            'htmx_alpine_form_views': CodeForDisplay(
                code=get_python_example_context('htmx_alpine_form_views.py'),
                language="Python",
            ),
            'form_main_template': CodeForDisplay(
                code=get_example_context('styleguide/htmx_alpine_crispy/main.html'),
                language="Django",
            ),
            'form_partial_template': CodeForDisplay(
                code=get_example_context('styleguide/htmx_alpine_crispy/partial_form.html'),
                language="Django",
            ),
            'htmx_alpine_form': CodeForDisplay(
                code=get_python_example_context('htmx_alpine_form_demo.py'),
                language="Python",
            ),
            'htmx_hq_hx_action': CodeForDisplay(
                code=get_python_example_context('htmx_hq_hx_action.py'),
                language="Python",
            ),
            'htmx_todo_main': CodeForDisplay(
                code=get_example_context('styleguide/htmx_todo/main.html'),
                language="Django",
            ),
            'htmx_todo_item': CodeForDisplay(
                code=get_example_context('styleguide/htmx_todo/item.html'),
                language="Django",
            ),
            'htmx_todo_item_done_swap': CodeForDisplay(
                code=get_example_context('styleguide/htmx_todo/item_done_oob_swap.html'),
                language="Django",
            ),
            'htmx_todo_item_done': CodeForDisplay(
                code=get_example_context('styleguide/htmx_todo/item_done.html'),
                language="Django",
            ),
            'loading_button': CodeForDisplayWithPartial(
                code=get_example_context('styleguide/bootstrap5/examples/htmx_loading_button.html'),
                partial="styleguide/bootstrap5/examples/htmx_loading_button.html",
                language="Django",
            ),
            'loading_checkbox': CodeForDisplayWithPartial(
                code=get_example_context('styleguide/bootstrap5/examples/htmx_loading_checkbox.html'),
                partial="styleguide/bootstrap5/examples/htmx_loading_checkbox.html",
                language="Django",
            ),
            'loading_form': CodeForDisplayWithPartial(
                code=get_example_context('styleguide/bootstrap5/examples/htmx_loading_form.html'),
                partial="styleguide/bootstrap5/examples/htmx_loading_form.html",
                language="Django",
            ),
        }
    })
    return render(request, 'styleguide/bootstrap5/htmx_and_alpine.html', context)


@use_bootstrap5
def styleguide_atoms_accessibility(request):
    return render(request, 'styleguide/bootstrap5/atoms/accessibility.html',
                  get_navigation_context("styleguide_atoms_accessibility_b5"))


@use_bootstrap5
def styleguide_atoms_typography(request):
    return render(request, 'styleguide/bootstrap5/atoms/typography.html',
                  get_navigation_context("styleguide_atoms_typography_b5"))


@use_bootstrap5
def styleguide_atoms_colors(request):
    context = get_navigation_context("styleguide_atoms_colors_b5")
    context.update({
        'interaction': get_interaction_colors(),
        'neutral': get_neutral_colors(),
        'gradient': get_gradient_colors(),
    })
    return render(request, 'styleguide/bootstrap5/atoms/colors.html', context)


@use_bootstrap5
def styleguide_atoms_icons(request):
    context = get_navigation_context("styleguide_atoms_icons_b5")
    context.update({
        'common_icons': get_common_icons(),
        'custom_icons': get_custom_icons(),
    })
    return render(request, 'styleguide/bootstrap5/atoms/icons.html', context)


@use_bootstrap5
def styleguide_molecules_buttons(request):
    context = get_navigation_context("styleguide_molecules_buttons_b5")
    context.update({
        'examples': {
            'most_buttons': get_example_context('styleguide/bootstrap5/examples/most_buttons.html'),
            'primary_action_buttons': get_example_context(
                'styleguide/bootstrap5/examples/primary_action_buttons.html'),
            'download_upload_buttons': get_example_context(
                'styleguide/bootstrap5/examples/download_upload_buttons.html'),
            'destructive_action_buttons': get_example_context(
                'styleguide/bootstrap5/examples/destructive_action_buttons.html'),
        }
    })
    return render(request, 'styleguide/bootstrap5/molecules/buttons.html', context)


@use_bootstrap5
def styleguide_molecules_selections(request):
    context = get_navigation_context("styleguide_molecules_selections_b5")
    context.update({
        'examples': {
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
        }
    })
    return render(request, 'styleguide/bootstrap5/molecules/selections.html', context)


@use_bootstrap5
def styleguide_molecules_checkboxes(request):
    context = get_navigation_context("styleguide_molecules_checkboxes_b5")
    context.update({
        'examples': {
            'switch': get_example_context('styleguide/bootstrap5/examples/switch.html'),
            'checkbox': get_example_context('styleguide/bootstrap5/examples/checkbox.html'),
            'checkbox_form': get_example_context('styleguide/bootstrap5/examples/checkbox_form.html'),
            'checkbox_horizontal_form': get_example_context(
                'styleguide/bootstrap5/examples/checkbox_horizontal_form.html'),
            'checkbox_crispy': CrispyFormsDemo(
                CheckboxDemoForm(), get_python_example_context('checkbox_form.py'),
            ),
            'switch_crispy': CrispyFormsDemo(
                SwitchDemoForm(), get_python_example_context('switch_form.py'),
            ),
        }
    })
    return render(request, 'styleguide/bootstrap5/molecules/checkboxes.html', context)


@use_bootstrap5
def styleguide_molecules_modals(request):
    context = get_navigation_context("styleguide_molecules_modals_b5")
    context.update({
        'examples': {
            'modal': get_example_context('styleguide/bootstrap5/examples/modal.html'),
            'modal_ko': HtmlWithJsDemo(
                code_html=get_html_example_context('modal_ko.html'),
                code_js=get_js_example_context('modal_ko.js'),
            ),
            'open_modal_ko': HtmlWithJsDemo(
                code_html=get_html_example_context('open_modal_ko.html'),
                code_js=get_js_example_context('open_modal_ko.js'),
            ),
            'open_remote_modal_ko': HtmlWithJsDemo(
                code_html=get_html_example_context('open_remote_modal_ko.html'),
                code_js=get_js_example_context('open_remote_modal_ko.js'),
            ),
            'remote_modal': get_example_context('styleguide/bootstrap5/examples/remote_modal.html'),
        }
    })
    return render(request, 'styleguide/bootstrap5/molecules/modals.html', context)


@use_bootstrap5
def styleguide_molecules_pagination(request):
    context = get_navigation_context("styleguide_molecules_pagination_b5")
    context.update({
        'examples': {
            'pagination': HtmlWithJsDemo(
                code_html=get_html_example_context('pagination.html'),
                code_js=get_js_example_context('pagination.js'),
            ),
            'htmx_pagination_data': CodeForDisplay(
                code=get_python_example_context('htmx_pagination_data.py'),
                language="Python",
            ),
            'htmx_pagination_host_view': CodeForDisplay(
                code=get_python_example_context('htmx_pagination_host_view.py'),
                language="Python",
            ),
            'htmx_pagination_table': CodeForDisplay(
                code=get_python_example_context('htmx_pagination_table.py'),
                language="Python",
            ),
            'htmx_pagination_table_view': CodeForDisplay(
                code=get_python_example_context('htmx_pagination_table_view.py'),
                language="Python",
            ),
            'htmx_pagination_template': CodeForDisplay(
                code=get_example_context('styleguide/bootstrap5/examples/htmx_pagination.html'),
                language="Django",
            ),
        }
    })
    return render(request, 'styleguide/bootstrap5/molecules/pagination.html', context)


@use_bootstrap5
def styleguide_molecules_searching(request):
    context = get_navigation_context("styleguide_molecules_searching_b5")
    context.update({
        'examples': {
            'search_box': HtmlWithJsDemo(
                code_html=get_html_example_context('search_box.html'),
                code_js=get_js_example_context('search_box.js'),
            ),
        }
    })
    return render(request, 'styleguide/bootstrap5/molecules/searching.html', context)


@use_bootstrap5
def styleguide_molecules_inline_editing(request):
    context = get_navigation_context("styleguide_molecules_inline_editing_b5")
    context.update({
        'examples': {
            'inline_edit': HtmlWithJsDemo(
                code_html=get_html_example_context('inline_edit.html'),
                code_js=get_js_example_context('inline_edit.js'),
            ),
            'inline_edit_lang': HtmlWithJsDemo(
                code_html=get_html_example_context('inline_edit_lang.html'),
                code_js=get_js_example_context('inline_edit_lang.js'),
            ),
        }
    })
    return render(request, 'styleguide/bootstrap5/molecules/inline_editing.html', context)


@use_bootstrap5
def styleguide_molecules_help(request):
    context = get_navigation_context("styleguide_molecules_help_b5")
    context.update({
        'examples': {
            'help': get_example_context('styleguide/bootstrap5/examples/help.html'),
        }
    })
    return render(request, 'styleguide/bootstrap5/molecules/help.html', context)


@use_bootstrap5
def styleguide_molecules_feedback(request):
    context = get_navigation_context("styleguide_molecules_feedback_b5")
    context.update({
        'examples': {
            'feedback': HtmlWithJsDemo(
                code_html=get_html_example_context('feedback.html'),
                code_js=get_js_example_context('feedback.js'),
            ),
        }
    })
    return render(request, 'styleguide/bootstrap5/molecules/feedback.html', context)


@use_bootstrap5
def styleguide_molecules_dates_times(request):
    context = get_navigation_context("styleguide_molecules_dates_times_b5")
    context.update({
        'examples': {
            'datepicker_widget': get_example_context('styleguide/bootstrap5/examples/datepicker_widget.html'),
            'date_only': HtmlWithJsDemo(
                code_html=get_html_example_context('date_only.html'),
                code_js=get_js_example_context('date_only.js'),
            ),
            'tempus_dominus': HtmlWithJsDemo(
                code_html=get_html_example_context('tempus_dominus.html'),
                code_js=get_js_example_context('tempus_dominus.js'),
            ),
            'date_range': HtmlWithJsDemo(
                code_html=get_html_example_context('date_range.html'),
                code_js=get_js_example_context('date_range.js'),
            ),
            'time_only': HtmlWithJsDemo(
                code_html=get_html_example_context('time_only.html'),
                code_js=get_js_example_context('time_only.js'),
            ),
            'time_only_24': HtmlWithJsDemo(
                code_html=get_html_example_context('time_only_24.html'),
                code_js=get_js_example_context('time_only_24.js'),
            ),
        }
    })
    return render(request, 'styleguide/bootstrap5/molecules/dates_times.html', context)


@use_bootstrap5
def styleguide_organisms_forms(request):
    crispy_errors_form = ErrorsCrispyExampleForm({'full_name': 'Jon Jackson'})
    crispy_errors_form.is_valid()
    context = get_navigation_context("styleguide_organisms_forms_b5")
    context.update({
        'examples': {
            'crispy_basic': CrispyFormsDemo(
                BasicCrispyExampleForm(), get_python_example_context('crispy_forms_basic.py'),
            ),
            'crispy_errors': CrispyFormsDemo(
                crispy_errors_form, get_python_example_context('crispy_forms_errors.py'),
            ),
            'crispy_disabled_fields': CrispyFormsDemo(
                DisabledFieldsExampleForm(), get_python_example_context('disabled_fields.py'),
            ),
            'crispy_placeholder_help_text': CrispyFormsDemo(
                PlaceholderHelpTextExampleForm(), get_python_example_context('placeholder_help_text.py'),
            ),
            'crispy_knockout': CrispyFormsWithJsDemo(
                form=KnockoutCrispyExampleForm(),
                code_python=get_python_example_context('crispy_forms_knockout.py'),
                code_js=get_js_example_context('crispy_forms_knockout.js'),
            ),
            'crispy_knockout_validation': CrispyFormsWithJsDemo(
                form=KnockoutValidationCrispyExampleForm(),
                code_python=get_python_example_context('crispy_forms_knockout_validation.py'),
                code_js=get_js_example_context('crispy_forms_knockout_validation.js'),
            ),
            'basic_form': get_example_context('styleguide/bootstrap5/examples/basic_form.html'),
            'form_invalid': get_example_context('styleguide/bootstrap5/examples/form_invalid.html'),
            'form_valid': get_example_context('styleguide/bootstrap5/examples/form_valid.html'),
            'disabled_fields': get_example_context('styleguide/bootstrap5/examples/disabled_fields.html'),
            'placeholder_help_text': get_example_context(
                'styleguide/bootstrap5/examples/placeholder_help_text.html'),
        }
    })
    return render(request, 'styleguide/bootstrap5/organisms/forms.html', context)


@use_bootstrap5
def styleguide_organisms_tables(request):
    context = get_navigation_context("styleguide_organisms_tables_b5")
    context.update({
        'examples': {
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
        },
    })
    return render(request, 'styleguide/bootstrap5/organisms/tables.html', context)


@use_bootstrap5
def styleguide_pages_navigation(request):
    context = get_navigation_context("styleguide_pages_navigation_b5")
    context.update({
        'examples': {
            'tabs': CodeForDisplay(
                code=get_python_example_context('tabs.py'),
                language="Python",
            ),
            'page_title_block': CodeForDisplay(
                code=get_example_context('styleguide/bootstrap5/examples/page_title_block.html'),
                language="HTML",
            ),
            'page_header': get_example_context('styleguide/bootstrap5/examples/page_header.html'),
            'navs_cards': get_example_context('styleguide/bootstrap5/examples/navs_cards.html'),
            'navs_tabs': get_example_context('styleguide/bootstrap5/examples/navs_tabs.html'),
        },
    })
    return render(request, 'styleguide/bootstrap5/pages/navigation.html', context)


@use_bootstrap5
def styleguide_pages_views(request):
    context = get_navigation_context("styleguide_pages_views_b5")
    context.update({
        'examples': {
            'functional_view': CodeForDisplay(
                code=get_python_example_context('functional_view.py'),
                language="Python",
            ),
            'class_view': CodeForDisplay(
                code=get_python_example_context('class_view.py'),
                language="Python",
            ),
            'example_urls': CodeForDisplay(
                code=get_python_example_context('example_urls.py'),
                language="Python",
            ),
            'simple_centered_page': CodeForDisplay(
                code=get_example_context('styleguide/bootstrap5/examples/simple_centered_page.html'),
                language="HTML",
            ),
            'simple_section': CodeForDisplay(
                code=get_example_context('styleguide/bootstrap5/examples/simple_section.html'),
                language="HTML",
            ),
        },
    })
    return render(request, 'styleguide/bootstrap5/pages/views.html', context)
