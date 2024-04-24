from django.shortcuts import render


def react_examples(request):
    return render(request, 'styleguide/react/reactExamples.html', {})
