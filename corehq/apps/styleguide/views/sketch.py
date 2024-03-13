from django.shortcuts import render

from corehq.apps.hqwebapp.decorators import use_bootstrap5


@use_bootstrap5
def test_sketch(request):
    return render(request, 'styleguide/sketch/test_sketch.html', {})
