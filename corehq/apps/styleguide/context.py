from collections import namedtuple

NavigationGroup = namedtuple('NavigationGroup', 'name pages')
Page = namedtuple('Page', 'name urlname')


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
                ],
            ),
        ],
    }
