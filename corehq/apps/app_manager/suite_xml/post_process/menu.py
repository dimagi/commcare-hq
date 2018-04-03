from __future__ import absolute_import
from __future__ import unicode_literals
from corehq.apps.app_manager import id_strings
from corehq.apps.app_manager.suite_xml.contributors import PostProcessor
from corehq.apps.app_manager.suite_xml.xml_models import Menu, Text


class GridMenuHelper(PostProcessor):

    def update_suite(self):
        """
        Ensure that there exists at least one menu where id="root".
        """
        if not self._contains_root_menu(self.suite.menus):
            self.suite.menus.append(Menu(id=id_strings.ROOT, text=Text(), style="grid"))

    @staticmethod
    def _contains_root_menu(menus):
        for menu in menus:
            if menu.id == id_strings.ROOT:
                return True
        return False
