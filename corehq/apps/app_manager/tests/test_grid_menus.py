from django.test import SimpleTestCase
from corehq.apps.app_manager.tests import AppFactory, TestXmlMixin


class GridMenuSuiteTests(SimpleTestCase, TestXmlMixin):

    def test_that_grid_style_is_added(self):
        """
        Confirms that style="grid" is added to the root menu
        """
        factory = AppFactory(build_version='2.24')
        factory.app.use_grid_menus = True
        factory.new_basic_module('registration', 'patient registration')
        factory.app.get_module(0).put_in_root = True
        factory.new_basic_module('visit', 'patient visit')
        factory.app.get_module(1).put_in_root = True

        suite = factory.app.create_suite()
        root_xpath = './menu[@id="root"]'
        self.assertXmlHasXpath(suite, root_xpath)
        self.assertXmlPartialEqual(
            """
            <partial>
                <menu id="root" style="grid">
                    <text><locale id="modules.m0"/></text>
                    <command id="m0-f0"/>
                </menu>
                <menu id="root" style="grid">
                    <text><locale id="modules.m1"/></text>
                    <command id="m1-f0"/>
                </menu>
            </partial>
            """,
            suite,
            root_xpath
        )

    def test_that_root_menu_added(self):
        """
        Confirms that a menu is added with id="root" and style="grid"
        when the app normally wouldn't have a menu with id="root".
        """
        factory = AppFactory(build_version='2.24')
        factory.app.use_grid_menus = True
        factory.new_basic_module('registration', 'patient')

        suite = factory.app.create_suite()
        root_xpath = './menu[@id="root"]'
        self.assertXmlHasXpath(suite, root_xpath)
        self.assertXmlPartialEqual(
            '<partial><menu id="root" style="grid"><text/></menu></partial>',
            suite,
            root_xpath
        )

    def test_use_grid_menus_is_false(self):
        """
        Confirms that style="grid" is not added to any menus when use_grid_menus is False.
        """
        factory = AppFactory(build_version='2.24')
        factory.app.use_grid_menus = False
        factory.new_basic_module('registration', 'patient')

        suite = factory.app.create_suite()
        style_xpath = './menu[@style="grid"]'
        self.assertXmlDoesNotHaveXpath(suite, style_xpath)
