from django.shortcuts import render

from corehq.apps.styleguide.context import get_navigation_context


def styleguide_home(request):
    return render(request, 'styleguide/bootstrap5/home.html', get_navigation_context("styleguide_home_b5"))


def styleguide_atoms_accessibility(request):
    return render(request, 'styleguide/bootstrap5/atoms/accessibility.html',
                  get_navigation_context("styleguide_atoms_accessibility_b5"))


def styleguide_atoms_typography(request):
    return render(request, 'styleguide/bootstrap5/atoms/typography.html',
                  get_navigation_context("styleguide_atoms_typography_b5"))
