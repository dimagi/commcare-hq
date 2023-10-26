from django.shortcuts import render

from corehq.apps.styleguide.context import (
    get_navigation_context,
    get_interaction_colors,
    get_neutral_colors,
    get_common_icons,
    get_custom_icons,
    get_example_context,
)


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
