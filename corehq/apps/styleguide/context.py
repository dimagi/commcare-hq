import os
from collections import namedtuple

NavigationGroup = namedtuple('NavigationGroup', 'name pages')
Page = namedtuple('Page', 'name urlname')
ColorGroup = namedtuple('ColorGroup', 'title description main_color')
Color = namedtuple('Color', 'slug hex')
CrispyFormsDemo = namedtuple('CrispyFormsDemo', 'form code')
CrispyFormsWithJsDemo = namedtuple('CrispyFormsWithJsDemo', 'form code_python code_js')


def get_navigation_context(current_page):
    return {
        'current_page': current_page,
        'sidebar': [
            NavigationGroup(
                name="Getting started",
                pages=[
                    Page("Introduction", 'styleguide_home_b5'),
                    Page("Code Guidelines", 'styleguide_code_guidelines_b5'),
                ],
            ),
            NavigationGroup(
                name="Atoms",
                pages=[
                    Page("Accessibility", 'styleguide_atoms_accessibility_b5'),
                    Page("Typography", 'styleguide_atoms_typography_b5'),
                    Page("Colors", 'styleguide_atoms_colors_b5'),
                    Page("Icons", 'styleguide_atoms_icons_b5'),
                ],
            ),
            NavigationGroup(
                name="Molecules",
                pages=[
                    Page("Buttons", 'styleguide_molecules_buttons_b5'),
                    Page("Selections", 'styleguide_molecules_selections_b5'),
                    Page("Checkboxes & Switches", 'styleguide_molecules_checkboxes_b5'),
                    Page("Modals", 'styleguide_molecules_modals_b5'),
                    Page("Pagination", 'styleguide_molecules_pagination_b5'),
                ],
            ),
        ],
    }


def get_interaction_colors():
    return [
        ColorGroup(
            title="Call to Action",
            description="Referred to as 'CommCare Blue'. "
                        "Use for buttons, checkmarks, radio buttons or actionable primary icons. "
                        "Links are a slightly darkened shade of this color to improve contrast.",
            main_color=Color('primary', '5D70D2'),
        ),
        ColorGroup(
            title="Download / Upload",
            description="Used typically for buttons indicating a download or upload action. "
                        "Corresponds with 'info' classes",
            main_color=Color('info', '01A2A9'),
        ),
        ColorGroup(
            title="Success",
            description="Use when an action has been completed successfully, primarily for messaging. "
                        "Rarely used for interactive elements like buttons.",
            main_color=Color('success', '3FA12A'),
        ),
        ColorGroup(
            title="Attention",
            description="Use for warning-level information, less severe than an error but still in "
                        "need of attention.",
            main_color=Color('warning', 'EEAE00'),
        ),
        ColorGroup(
            title="Error, Negative Attention",
            description="Use to highlight an error, something negative or a critical risk. "
                        "Use as text, highlights, banners or destructive buttons. ",
            main_color=Color('danger', 'E73C27'),
        ),
    ]


def get_neutral_colors():
    return [
        ColorGroup(
            title="Text",
            description="Used for the main text color.",
            main_color=Color('dark', '343A40'),
        ),
        ColorGroup(
            title="Neutral",
            description="Use for neutral visual indicators, typically borders or backgrounds.",
            main_color=Color('secondary', '6C757D'),
        ),
        ColorGroup(
            title="Background",
            description="Used for backgrounds that are light but distinct from the default white background, "
                        "such as cards.",
            main_color=Color('light', 'F8F9FA'),
        ),
    ]


def get_common_icons():
    return [
        {
            'name': 'Common FontAwesome primary icons',
            'icons': [
                'fa-plus', 'fa-trash', 'fa-remove', 'fa-search',
                'fa-angle-double-right', 'fa-angle-double-down',
            ],
        },
        {
            'name': 'Common FontAwesome secondary icons',
            'icons': [
                'fa-cloud-download', 'fa-cloud-upload',
                'fa-warning', 'fa-info-circle', 'fa-question-circle', 'fa-check',
                'fa-external-link',
            ],
        }
    ]


def get_custom_icons():
    return [
        {
            'name': 'Custom HQ icons',
            'icons': [
                'fcc-flower', 'fcc-applications', 'fcc-commtrack', 'fcc-reports', 'fcc-data', 'fcc-users',
                'fcc-settings', 'fcc-help', 'fcc-exchange', 'fcc-messaging', 'fcc-chart-report',
                'fcc-form-report', 'fcc-datatable-report', 'fcc-piegraph-report', 'fcc-survey',
                'fcc-casemgt', 'fcc-blankapp', 'fcc-globe', 'fcc-app-createform', 'fcc-app-updateform',
                'fcc-app-completeform', 'fcc-app-biometrics',
            ],
        },
        {
            'name': 'Custom HQ icons specific to form builder',
            'icons': [
                'fcc-fd-text', 'fcc-fd-numeric', 'fcc-fd-data', 'fcc-fd-variable', 'fcc-fd-single-select',
                'fcc-fd-single-circle', 'fcc-fd-multi-select', 'fcc-fd-multi-box', 'fcc-fd-decimal',
                'fcc-fd-long', 'fcc-fd-datetime', 'fcc-fd-audio-capture', 'fcc-fd-android-intent',
                'fcc-fd-signature', 'fcc-fd-multi-box', 'fcc-fd-single-circle', 'fcc-fd-hash',
                'fcc-fd-external-case', 'fcc-fd-external-case-data', 'fcc-fd-expand', 'fcc-fd-collapse',
                'fcc-fd-case-property', 'fcc-fd-edit-form',
            ],
        },
    ]


def get_example_context(filename):
    examples = os.path.join(os.path.dirname(__file__), 'templates')
    with open(os.path.join(examples, filename), 'r', encoding='utf-8') as content:
        return content.read()


def get_crispy_forms_context(filename):
    examples = os.path.join(os.path.dirname(__file__), 'examples', 'bootstrap5')
    with open(os.path.join(examples, filename), 'r', encoding='utf-8') as content:
        return content.read()


def get_js_example_context(filename):
    examples = os.path.join(os.path.dirname(__file__), 'static', 'styleguide', 'js_examples')
    with open(os.path.join(examples, filename), 'r', encoding='utf-8') as content:
        return content.read()
