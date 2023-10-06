from collections import namedtuple

NavigationGroup = namedtuple('NavigationGroup', 'name pages')
Page = namedtuple('Page', 'name urlname')
ColorGroup = namedtuple('ColorGroup', 'title description main_color')
Color = namedtuple('Color', 'slug hex')


def get_navigation_context(current_page):
    return {
        'current_page': current_page,
        'sidebar': [
            NavigationGroup(
                name="Getting started",
                pages=[
                    Page("Introduction", 'styleguide_home_b5'),
                ],
            ),
            NavigationGroup(
                name="Atoms",
                pages=[
                    Page("Accessibility", 'styleguide_atoms_accessibility_b5'),
                    Page("Typography", 'styleguide_atoms_typography_b5'),
                    Page("Colors", 'styleguide_atoms_colors_b5'),
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
