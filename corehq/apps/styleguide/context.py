import os
from collections import namedtuple

NavigationGroup = namedtuple('NavigationGroup', 'name pages')
Page = namedtuple('Page', 'name urlname')
ColorGroup = namedtuple('ColorGroup', 'title description main_color subtle_color')
Color = namedtuple('Color', 'slug hex')
CrispyFormsDemo = namedtuple('CrispyFormsDemo', 'form code')
CrispyFormsWithJsDemo = namedtuple('CrispyFormsWithJsDemo', 'form code_python code_js')
CodeForDisplay = namedtuple('CodeForDisplay', 'code language')
ThemeColor = namedtuple('ThemeColor', 'slug hex theme_equivalent')


def get_navigation_context(current_page):
    return {
        'current_page': current_page,
        'sidebar': [
            NavigationGroup(
                name="Getting started",
                pages=[
                    Page("Introduction", 'styleguide_home_b5'),
                    Page("Code Guidelines", 'styleguide_code_guidelines_b5'),
                    Page("Bootstrap Migration Guide", 'styleguide_migration_guide_b5'),
                    Page("Javascript Guide", 'styleguide_javascript_guide_b5'),
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
                    Page("Searching & Filtering", 'styleguide_molecules_searching_b5'),
                    Page("Inline Editing", 'styleguide_molecules_inline_editing_b5'),
                    Page("Feedback", 'styleguide_molecules_feedback_b5'),
                    Page("Dates & Times", 'styleguide_molecules_dates_times_b5'),
                ],
            ),
            NavigationGroup(
                name="Organisms",
                pages=[
                    Page("Forms", 'styleguide_organisms_forms_b5'),
                    Page("Tables", 'styleguide_organisms_tables_b5'),
                ],
            ),
            NavigationGroup(
                name="Pages",
                pages=[
                    Page("Navigation", 'styleguide_pages_navigation_b5'),
                    Page("Views", 'styleguide_pages_views_b5'),
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
                        "Links are a slightly darkened shade of this color ($blue-600) to improve contrast.",
            main_color=Color('primary', '5D70D2'),
            subtle_color=Color('primary-subtle', 'DFE2H6'),
        ),
        ColorGroup(
            title="Download / Upload",
            description="Used typically for buttons indicating a download or upload action. "
                        "Corresponds with 'info' classes",
            main_color=Color('info', '01A2A9'),
            subtle_color=Color('info-subtle', 'CCECEE'),
        ),
        ColorGroup(
            title="Success",
            description="Use when an action has been completed successfully, primarily for messaging. "
                        "Rarely used for interactive elements like buttons.",
            main_color=Color('success', '3FA12A'),
            subtle_color=Color('success-subtle', 'D9ECD4'),
        ),
        ColorGroup(
            title="Attention",
            description="Use for warning-level information, less severe than an error but still in "
                        "need of attention.",
            main_color=Color('warning', 'EEAE00'),
            subtle_color=Color('warning-subtle', 'FCEFCC'),
        ),
        ColorGroup(
            title="Error, Negative Attention",
            description="Use to highlight an error, something negative or a critical risk. "
                        "Use as text, highlights, banners or destructive buttons. ",
            main_color=Color('danger', 'E73C27'),
            subtle_color=Color('danger-subtle', 'FAD8D4'),
        ),
    ]


def get_neutral_colors():
    return [
        ColorGroup(
            title="Text",
            description="Used for the main text color.",
            main_color=Color('dark', '343A40'),
            subtle_color=None,
        ),
        ColorGroup(
            title="Neutral",
            description="Use for neutral visual indicators, typically borders or backgrounds.",
            main_color=Color('secondary', '6C757D'),
            subtle_color=None,
        ),
        ColorGroup(
            title="Background",
            description="Used for backgrounds that are light but distinct from the default white background, "
                        "such as cards.",
            main_color=Color('light', 'F8F9FA'),
            subtle_color=None,
        ),
    ]


def get_gradient_colors():
    return {
        'blue': [
            Color('blue-100', 'DFE2F6'),
            Color('blue-200', 'BEC6ED'),
            Color('blue-300', '9EA9E4'),
            Color('blue-400', '7D8DDB'),
            ThemeColor('blue-500', '5D70D2', theme_equivalent='primary'),
            Color('blue-600', '4A5AA8'),
            Color('blue-700', '38437E'),
            Color('blue-800', '252D54'),
            Color('blue-900', '13162A'),
        ],
        'gray': [
            ThemeColor('gray-100', 'f8f9fa', theme_equivalent='light'),
            Color('gray-200', 'e9ecef'),
            Color('gray-300', 'dee2e6'),
            Color('gray-400', 'ced4da'),
            Color('gray-500', 'adb5bd'),
            ThemeColor('gray-600', '6c757d', theme_equivalent='secondary'),
            Color('gray-700', '495057'),
            ThemeColor('gray-800', '343a40', theme_equivalent='dark'),
            Color('gray-900', '212529'),
        ],
        'slices': [
            Color('indigo', '3843D0'),
            Color('purple', '694aaa'),
            Color('pink', '9a5183'),
            Color('salmon', 'cb585d'),
            Color('orange', 'FC5F36'),
        ],
        'dimagi': [
            Color('dimagi-deep-purple', '16006D'),
            ThemeColor('dimagi-indigo', '3843D0', theme_equivalent='indigo'),
            Color('dimagi-sky', '8EA1FF'),
            ThemeColor('dimagi-marigold', 'FEAF31', theme_equivalent='yellow'),
            ThemeColor('dimagi-mango', 'FC5F36', theme_equivalent='orange'),
            ThemeColor('dimagi-sunset', 'E44434', theme_equivalent='red'),
        ],
        'indigo': [
            Color('indigo-100', 'd7d9f6'),
            Color('indigo-200', 'afb4ec'),
            Color('indigo-300', '888ee3'),
            Color('indigo-400', '6069d9'),
            Color('indigo-500', '3843D0'),
            Color('indigo-600', '2d36a6'),
            Color('indigo-700', '22287d'),
            Color('indigo-800', '161b53'),
            Color('indigo-900', '0b0d2a'),
        ],
        'purple': [
            Color('purple-100', 'e1dbee'),
            Color('purple-200', 'c3b7dd'),
            Color('purple-300', 'a592cc'),
            Color('purple-400', '876ebb'),
            Color('purple-500', '694aaa'),
            Color('purple-600', '543b88'),
            Color('purple-700', '3f2c66'),
            Color('purple-800', '2a1e44'),
            Color('purple-900', '150f22'),
        ],
        'pink': [
            Color('pink-100', 'ebdce6'),
            Color('pink-200', 'd7b9cd'),
            Color('pink-300', 'c297b5'),
            Color('pink-400', 'ae749c'),
            Color('pink-500', '9a5183'),
            Color('pink-600', '7b4169'),
            Color('pink-700', '5c314f'),
            Color('pink-800', '3e2034'),
            Color('pink-900', '1f101a'),
        ],
        'salmon': [
            Color('salmon-100', 'f5dedf'),
            Color('salmon-200', 'eabcbe'),
            Color('salmon-300', 'e09b9e'),
            Color('salmon-400', 'd5797d'),
            Color('salmon-500', 'cb585d'),
            Color('salmon-600', 'a2464a'),
            Color('salmon-700', '7a3538'),
            Color('salmon-800', '512325'),
            Color('salmon-900', '291213'),
        ],
    }


def _add_prefix_to_icons(prefix, icon_list):
    return [f"{prefix} {icon}" for icon in icon_list]


def get_common_icons():
    return [
        {
            'name': 'Common FontAwesome primary icons',
            'icons': _add_prefix_to_icons('fa-solid', [
                'fa-plus', 'fa-remove', 'fa-search', 'fa-angle-double-right', 'fa-angle-double-down',
            ]) + _add_prefix_to_icons('fa-regular', ['fa-trash-can']),
        },
        {
            'name': 'Common FontAwesome secondary icons',
            'icons': _add_prefix_to_icons('fa-solid', [
                'fa-cloud-download', 'fa-cloud-upload', 'fa-warning', 'fa-info-circle', 'fa-question-circle',
                'fa-check', 'fa-external-link',
            ]),
        }
    ]


def get_custom_icons():
    return [
        {
            'name': 'Custom HQ icons',
            'icons': _add_prefix_to_icons('fcc', [
                'fcc-flower', 'fcc-applications', 'fcc-commtrack', 'fcc-reports', 'fcc-data', 'fcc-users',
                'fcc-settings', 'fcc-help', 'fcc-exchange', 'fcc-messaging', 'fcc-chart-report',
                'fcc-form-report', 'fcc-datatable-report', 'fcc-piegraph-report', 'fcc-survey',
                'fcc-casemgt', 'fcc-blankapp', 'fcc-globe', 'fcc-app-createform', 'fcc-app-updateform',
                'fcc-app-completeform', 'fcc-app-biometrics',
            ]),
        },
        {
            'name': 'Custom HQ icons specific to form builder',
            'icons': _add_prefix_to_icons('fcc', [
                'fcc-fd-text', 'fcc-fd-numeric', 'fcc-fd-data', 'fcc-fd-variable', 'fcc-fd-single-select',
                'fcc-fd-single-circle', 'fcc-fd-multi-select', 'fcc-fd-multi-box', 'fcc-fd-decimal',
                'fcc-fd-long', 'fcc-fd-datetime', 'fcc-fd-audio-capture', 'fcc-fd-android-intent',
                'fcc-fd-signature', 'fcc-fd-multi-box', 'fcc-fd-single-circle', 'fcc-fd-hash',
                'fcc-fd-external-case', 'fcc-fd-external-case-data', 'fcc-fd-expand', 'fcc-fd-collapse',
                'fcc-fd-case-property', 'fcc-fd-edit-form',
            ]),
        },
    ]


def get_example_context(filename):
    examples = os.path.join(os.path.dirname(__file__), 'templates')
    with open(os.path.join(examples, filename), 'r', encoding='utf-8') as content:
        return content.read()


def get_python_example_context(filename):
    examples = os.path.join(os.path.dirname(__file__), 'examples', 'bootstrap5')
    with open(os.path.join(examples, filename), 'r', encoding='utf-8') as content:
        return content.read()


def get_js_example_context(filename):
    examples = os.path.join(os.path.dirname(__file__), 'static', 'styleguide', 'js_examples')
    with open(os.path.join(examples, filename), 'r', encoding='utf-8') as content:
        return content.read()
