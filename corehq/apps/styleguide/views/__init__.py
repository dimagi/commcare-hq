import os

from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.generic import *

from corehq.apps.styleguide.context import (
    get_common_icons,
    get_custom_icons,
)
from corehq.apps.styleguide.example_forms import (
    BasicCrispyForm,
    CheckboxesForm,
)


def styleguide_default(request):
    return HttpResponseRedirect(reverse(MainStyleGuideView.urlname))


class MainStyleGuideView(TemplateView):
    template_name = 'styleguide/bootstrap3/home.html'
    urlname = 'styleguide_home'


class BaseStyleGuideArticleView(TemplateView):
    template_name = 'styleguide/bootstrap3/base_section.html'

    @property
    def sections(self):
        """This will be inserted into the page context's sections variable
        as a list of strings following the format
        'styleguide/bootstrap3/_includes/<section>.html'
        Make sure you create the corresponding template in the styleguide app.

        :return: List of the sections in order. Usually organized by
        <article>/<section_name>
        """
        raise NotImplementedError("please implement 'sections'")

    @property
    def navigation_name(self):
        """This will be inserted into the page context under
        styleguide/bootstrap3/_includes/nav/<navigation_name>.html. Make sure
        you create the corresponding template in the styleguide app
        when you add this.
        :return: a string that is the name of the navigation section
        """
        raise NotImplementedError("please implement 'navigation_name'")

    @property
    def section_context(self):
        return {
            'sections': ['styleguide/bootstrap3/_includes/%s.html' % s
                         for s in self.sections],
            'navigation': ('styleguide/bootstrap3/_includes/nav/%s.html'
                           % self.navigation_name),
        }

    @property
    def page_context(self):
        """It's intended that you override this method when necessary to provide
        any additional content that's relevant to the view specifically.
        :return: a dict
        """
        return {}

    def example(self, filename):
        examples = os.path.join(os.path.dirname(__file__),
                                '..', 'templates', 'styleguide', 'bootstrap3', 'examples')
        with open(os.path.join(examples, filename), 'r', encoding='utf-8') as content:
            return content.read()

    def render_to_response(self, context, **response_kwargs):
        context.update(self.section_context)
        context.update(self.page_context)
        return super(BaseStyleGuideArticleView, self).render_to_response(
            context, **response_kwargs)


class AtomsStyleGuideView(BaseStyleGuideArticleView):
    urlname = 'styleguide_atoms'
    navigation_name = 'atoms'

    @property
    def sections(self):
        return [
            'atoms/intro',
            'atoms/accessibility',
            'atoms/typography',
            'atoms/colors',
            'atoms/icons',
            'atoms/css',
        ]

    @property
    def page_context(self):
        return {
            'common_icons': get_common_icons(),
            'custom_icons': get_custom_icons(),
            'swatches': {
                'RED': {
                    'main': ('e73c27', 'cc-att-neg-mid'),
                    'shades': [
                        ('fbeae6', 'cc-att-neg-extra-hi'),
                        ('fead9a', 'cc-att-neg-hi'),
                        ('bf0712', 'cc-att-neg-low'),
                        ('340101', 'cc-att-neg-extra-low'),
                    ],
                    'inverse': True,
                    'name': 'Error, Negative Attention',
                    'description': '''
                        Use to highlight an error, something negative or a critical risk.
                        Use as text, highlights, banners or destructive buttons. Often called
                        "danger", as in <code>.btn-danger</code>.
                    ''',
                },
                'YELLOW': {
                    'main': ('eec200', 'cc-light-warm-accent-mid'),
                    'shades': [
                        ('fcf2cd', 'cc-light-warm-accent-extra-hi'),
                        ('ffea8a', 'cc-light-warm-accent-hi'),
                        ('9c6f19', 'cc-light-warm-accent-low'),
                        ('573b00', 'cc-light-warm-accent-extra-low'),
                    ],
                    'name': 'Attention',
                    'description': '''
                        Use for warning-level information, less severe than an error but still in need of
                        attention. Often called "warning", as in <code>.alert-warning</code>.
                    ''',
                },
                'GREEN': {
                    'main': ('4aba32', 'cc-att-pos-mid'),
                    'shades': [
                        ('e3f1df', 'cc-att-pos-extra-hi'),
                        ('bbe5b3', 'cc-att-pos-hi'),
                        ('118043', 'cc-att-pos-low'),
                        ('173630', 'cc-att-pos-extra-low'),
                    ],
                    'inverse': True,
                    'name': 'Success',
                    'description': '''
                        Use when an action has been completed successfully, primarily for messaging.
                        Rarely used for interacactive elements like buttons. Used in classes such as
                        <code>.alert-success</code>.
                    ''',
                },
                'BLACK': {
                    'main': ('1c2126', 'cc-text'),
                    'inverse': True,
                    'name': 'Ink Black',
                    'description': "Default text color. Also used for footer.",
                },
                'BACKGROUND': {
                    'main': ('f2f2f1', 'cc-bg'),
                    'name': 'Background',
                    'description': '''
                        Used for backgrounds that are light but distinct from the default white background,
                        such as panel headers.
                    ''',
                },
                'ACTION': {
                    'main': ('5c6ac5', 'call-to-action-mid'),
                    'shades': [
                        ('f4f5fa', 'call-to-action-extra-hi'),
                        ('b4bcf5', 'call-to-action-hi'),
                        ('212f78', 'call-to-action-low'),
                        ('000639', 'call-to-action-extra-low'),
                    ],
                    'inverse': True,
                    'name': 'Call to Action',
                    'description': '''
                        Use for buttons, checkmarks, radio buttons or actionable primary icons.
                        Do not use for text links. Used for <code>.btn-primary</code>.
                    ''',
                },
                'ACCENT_TEAL': {
                    'main': ('00bdc5', 'cc-light-cool-accent-mid'),
                    'shades': [
                        ('ccf3f4', 'cc-light-cool-accent-hi'),
                        ('00799a', 'cc-light-cool-accent-low'),
                    ],
                    'inverse': True,
                    'name': 'Accent Teal',
                    'description': '''
                        Use for primary button on dark backgrounds.
                        Use sparingly for secondary buttons, typically buttons indicating a download or upload.
                        Corresponds with "info" classes like <code>.btn-info</code>.
                    ''',
                },
                'SIGNUP_PURPLE': {
                    'main': ('43467F', 'color-purple-dark'),
                    'inverse': True,
                    'name': 'Signup Purple',
                    'description': "Use for banners or interactive elements in the signup and registration flow.",
                },
                'SIGNUP_PURPLE_INVERSE': {
                    'main': ('E3D0FF', 'color-purple-dark-inverse'),
                    'name': '',
                    'description': "Corresponds to signup purple."
                },
                'NEUTRAL': {
                    'main': ('685c53', 'cc-neutral-mid'),
                    'shades': [
                        ('d6d6d4', 'cc-neutral-hi'),
                        ('373534', 'cc-neutral-low'),
                    ],
                    'inverse': True,
                    'name': 'Neutral',
                    'description': '''
                        Use for neutral visual indicators, typically borders or backgrounds.
                    ''',
                },
                'BLUE': {
                    'main': ('004ebc', 'cc-brand-mid'),
                    'shades': [
                        ('bcdeff', 'cc-brand-hi'),
                        ('002c5f', 'cc-brand-low'),
                    ],
                    'inverse': True,
                    'name': 'Link, Selection',
                    'description': '''
                        Use for text links or to indicate that something is selected. Used in <code>.active</code>.
                    ''',
                },
                'ACCENT_PURPLE': {
                    'main': ('9060c8', 'cc-dark-cool-accent-mid'),
                    'shades': [
                        ('d6c5ea', 'cc-dark-cool-accent-hi'),
                        ('5d3f82', 'cc-dark-cool-accent-low'),
                    ],
                    'inverse': True,
                    'name': 'Accent Purple',
                    'description': '''
                        Avoid. Used occasionally for billing, web apps, and other unusual cases.
                    ''',
                },
                'ACCENT_ORANGE': {
                    'main': ('ff8400', 'cc-dark-warm-accent-mid'),
                    'shades': [
                        ('ffe3c2', 'cc-dark-warm-accent-hi'),
                        ('994f00', 'cc-dark-warm-accent-low'),
                    ],
                    'inverse': True,
                    'name': 'Accent Orange',
                    'description': '''
                        Avoid. Used occasionally for billing, web apps, and other unusual cases.
                    ''',
                },
            },
        }


class MoleculesStyleGuideView(BaseStyleGuideArticleView):
    urlname = 'styleguide_molecules'
    navigation_name = 'molecules'

    @property
    def sections(self):
        return [
            'molecules/intro',
            'molecules/buttons',
            'molecules/selections',
            'molecules/checkboxes',
            'molecules/modals',
            'molecules/pagination',
            'molecules/search_box',
            'molecules/inline_edit',
            'molecules/feedback',
        ]

    @property
    def page_context(self):
        return {
            'checkboxes_form': CheckboxesForm(),
            'examples': {
                'selections': {
                    'button_group': self.example('button_group.html'),
                    'select2': self.example('select2.html'),
                    'multiselect': self.example('multiselect.html'),
                },
                'checkbox_in_form': self.example('checkbox_in_form.html'),
                'lonely_checkbox': self.example('lonely_checkbox.html'),
                'modals': self.example('modals.html'),
                'pagination': self.example('pagination.html'),
                'search_box': self.example('search_box.html'),
                'inline_edit': self.example('inline_edit.html'),
                'feedback': self.example('feedback.html'),
            },
        }


class OrganismsStyleGuideView(BaseStyleGuideArticleView):
    urlname = 'styleguide_organisms'
    navigation_name = 'organisms'

    @property
    def sections(self):
        return [
            'organisms/intro',
            'organisms/forms',
            'organisms/tables',
        ]

    @property
    def page_context(self):
        return {
            'basic_crispy_form': BasicCrispyForm(),
            'examples': {
                'html_form': self.example('html_form.html'),
                'error_form': self.example('error_form.html'),
                'basic_table': self.example('basic_table.html'),
                'complex_table': self.example('complex_table.html'),
            },
        }


class PagesStyleGuideView(BaseStyleGuideArticleView):
    urlname = 'styleguide_pages'
    navigation_name = 'pages'

    @property
    def sections(self):
        return [
            'pages/intro',
            'pages/navigation',
            'pages/class_based',
            'pages/functional',
        ]

    @property
    def page_context(self):
        return {
            'examples': {
                'header': self.example('header.html'),
                'panels': self.example('panels.html'),
                'tabs': self.example('tabs.html'),
            },
        }
