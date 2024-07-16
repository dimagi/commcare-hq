from django.shortcuts import render
from corehq.apps.styleguide.context import (
    get_example_context,
    get_js_example_context,
    get_react_example_context,
    get_local_react_example_context
)


def pagination(request):
    context = {}
    context['examples'] = {
        'paginationSync': {
            'code': get_local_react_example_context('paginationSync.js'),
            'language': 'JSX',
        },
        'paginationAsync': {
            'code': get_local_react_example_context('paginationAsync.js'),
            'language': 'JSX',
        },
        'componentCode': {
            'code': get_local_react_example_context('components', 'pagination.js'),
            'language': 'JSX',
        },
    }

    return render(request, 'styleguide/react/pagination.html', context)


def react_examples(request):
    context = {}
    print('context is: ', get_example_context('styleguide/react/partials/formPopup.html'))
    context['markup'] = {
        'form_popup': {
            'code': get_example_context('styleguide/react/partials/formPopup.html'),
            'language': 'HTML',
        },
        'readFromKnockout': {
            'code': get_example_context('styleguide/react/partials/readFromKnockout.html'),
            'language': 'HTML',
        },
        'reactToHTML': {
            'code': get_example_context('styleguide/react/partials/reactToHTML.html'),
            'language': 'HTML',
        },
        'localTable': {
            'code': get_example_context('styleguide/react/partials/localTable.html'),
            'language': 'HTML',
        },
        'remoteTable': {
            'code': get_example_context('styleguide/react/partials/remoteTable.html'),
            'language': 'HTML',
        },
        'buttonTable': {
            'code': get_example_context('styleguide/react/partials/buttonTable.html'),
            'language': 'HTML',
        },
    }
    context['examples'] = {
        'form_popup': {
            'code': get_react_example_context('modalPopup.js'),
            'language': 'JSX',
        },
        'readFromKnockout': {
            'code': get_react_example_context('readFromKnockout.js'),
            'language': 'JSX',
        },
        'koTest': {
            'code': get_js_example_context('ko-test.js'),
            'language': 'JS',
        },
        'reactToHTML': {
            'code': get_react_example_context('reactToHTML.js'),
            'language': 'JSX',
        },
        'localTable': {
            'code': get_react_example_context('localTable.js'),
            'language': 'JSX',
        },
        'remoteTable': {
            'code': get_react_example_context('remoteTable.js'),
            'language': 'JSX',
        },
        'buttonTable': {
            'code': get_react_example_context('buttonTable.js'),
            'language': 'JSX',
        },
    }
    return render(request, 'styleguide/react/reactExamples.html', context)
