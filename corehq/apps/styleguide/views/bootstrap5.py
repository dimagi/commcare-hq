from django.shortcuts import render

from corehq.apps.hqwebapp.decorators import use_bootstrap5
from corehq.apps.styleguide.context import (
    get_navigation_context,
    get_interaction_colors,
    get_neutral_colors,
    get_common_icons,
    get_custom_icons,
    get_example_context,
    get_crispy_forms_context,
    CrispyFormsDemo,
    CrispyFormsWithJsDemo,
    get_js_example_context,
)
from corehq.apps.styleguide.examples.bootstrap5.checkbox_form import CheckboxDemoForm
from corehq.apps.styleguide.examples.bootstrap5.switch_form import SwitchDemoForm


def styleguide_home(request):
    return render(request, 'styleguide/bootstrap5/home.html', get_navigation_context("styleguide_home_b5"))


def styleguide_code_guidelines(request):
    return render(request, 'styleguide/bootstrap5/code_guidelines.html',
                  get_navigation_context("styleguide_code_guidelines_b5"))


def styleguide_atoms_accessibility(request):
    return render(request, 'styleguide/bootstrap5/atoms/accessibility.html',
                  get_navigation_context("styleguide_atoms_accessibility_b5"))


def styleguide_atoms_typography(request):
    return render(request, 'styleguide/bootstrap5/atoms/typography.html',
                  get_navigation_context("styleguide_atoms_typography_b5"))


def styleguide_atoms_colors(request):
    context = get_navigation_context("styleguide_atoms_colors_b5")
    context.update({
        'interaction': get_interaction_colors(),
        'neutral': get_neutral_colors(),
    })
    return render(request, 'styleguide/bootstrap5/atoms/colors.html', context)


def styleguide_atoms_icons(request):
    context = get_navigation_context("styleguide_atoms_icons_b5")
    context.update({
        'common_icons': get_common_icons(),
        'custom_icons': get_custom_icons(),
    })
    return render(request, 'styleguide/bootstrap5/atoms/icons.html', context)


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


def styleguide_molecules_selections(request):
    context = get_navigation_context("styleguide_molecules_selections_b5")
    context.update({
        'examples': {
            'toggles': get_example_context('styleguide/bootstrap5/examples/toggles.html'),
            'select2_manual': get_example_context('styleguide/bootstrap5/examples/select2_manual.html'),
            'select2_css_class': get_example_context('styleguide/bootstrap5/examples/select2_css_class.html'),
            'select2_css_class_multiple': get_example_context(
                'styleguide/bootstrap5/examples/select2_css_class_multiple.html'),
            'select2_ko_dynamic': get_example_context('styleguide/bootstrap5/examples/select2_ko_dynamic.html'),
            'select2_ko_static': get_example_context('styleguide/bootstrap5/examples/select2_ko_static.html'),
            'select2_ko_autocomplete': get_example_context(
                'styleguide/bootstrap5/examples/select2_ko_autocomplete.html'),
            'multiselect': get_example_context('styleguide/bootstrap5/examples/multiselect.html'),
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
                CheckboxDemoForm(), get_crispy_forms_context('checkbox_form.py'),
            ),
            'switch_crispy': CrispyFormsDemo(
                SwitchDemoForm(), get_crispy_forms_context('switch_form.py'),
            ),
        }
    })
    return render(request, 'styleguide/bootstrap5/molecules/checkboxes.html', context)
