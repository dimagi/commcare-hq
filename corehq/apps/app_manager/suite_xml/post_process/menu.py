from corehq.apps.app_manager import id_strings
from corehq.apps.app_manager.suite_xml.contributors import PostProcessor
from corehq.apps.app_manager.suite_xml.sections.entries import EntriesHelper
from corehq.apps.app_manager.suite_xml.xml_models import Menu, Text
from corehq.util.timer import time_method


def _get_root_menu(menus):
    for menu in menus:
        if menu.id == id_strings.ROOT:
            return menu


class GridMenuHelper(PostProcessor):
    """This is pretty simple: it just adds a root menu if one isn't already present."""

    @time_method()
    def update_suite(self):
        """Ensure that there exists at least one menu where id="root"."""
        if not _get_root_menu(self.suite.menus):
            self.suite.menus.append(Menu(id=id_strings.ROOT, text=Text(), style="grid"))


class RootMenuAssertionsHelper(PostProcessor):
    """Set app-level custom assertions on root menu, creating one if necessary"""

    @time_method()
    def update_suite(self):
        root_menu = _get_root_menu(self.suite.menus)
        if not root_menu:
            root_menu = Menu(id=id_strings.ROOT, text=Text())
            self.suite.menus.append(root_menu)

        for id, assertion in enumerate(self.app.custom_assertions):
            root_menu.assertions.append(EntriesHelper.get_assertion(
                assertion.test,
                id_strings.custom_assertion_locale(id),
            ))
