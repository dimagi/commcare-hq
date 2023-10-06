from django.shortcuts import render

from corehq.apps.styleguide.context import (
    get_navigation_context,
    get_interaction_colors,
    get_neutral_colors,
)


def styleguide_home(request):
    return render(request, 'styleguide/bootstrap5/home.html', get_navigation_context("styleguide_home_b5"))


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
