from django.test import TestCase

from corehq.apps.app_manager.tests.app_factory import AppFactory
from corehq.apps.app_manager.tests.util import TestXmlMixin, patch_get_xform_resource_overrides


@patch_get_xform_resource_overrides()
class GridMenuSuiteTests(TestCase, TestXmlMixin):
    def test_that_grid_style_is_added(self, *args):
        """
        Confirms that style="grid" is added to the root menu
        """
        factory = AppFactory(build_version='2.24.0')
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

    def test_that_root_menu_added(self, *args):
        """
        Confirms that a menu is added with id="root" and style="grid"
        when the app normally wouldn't have a menu with id="root".
        """
        factory = AppFactory(build_version='2.24.0')
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

    def test_use_grid_menus_is_false(self, *args):
        """
        Confirms that style="grid" is not added to any menus when use_grid_menus is False.
        """
        factory = AppFactory(build_version='2.24.0')
        factory.app.use_grid_menus = False
        factory.new_basic_module('registration', 'patient')

        suite = factory.app.create_suite()
        style_xpath = './menu[@style="grid"]'
        self.assertXmlDoesNotHaveXpath(suite, style_xpath)

    def test_grid_menu_for_none(self, *args):
        factory = AppFactory(build_version='2.24.3')
        factory.app.create_profile()
        factory.app.grid_form_menus = 'none'
        factory.new_basic_module('registration', 'patient')
        factory.app.get_module(0).display_style = 'grid'
        root_xpath = './menu[@id="root"]'
        m0_xpath = './menu[@id="m0"]'

        # with Modules Menu to be list should not render root menu and render module w/o style=grid
        factory.app.use_grid_menus = False
        suite = factory.app.create_suite()
        self.assertXmlDoesNotHaveXpath(suite, root_xpath)
        self.assertXmlPartialEqual(
            '<partial><menu id="m0"><text><locale id="modules.m0"/></text><command id="m0-f0"/></menu></partial>',
            suite,
            m0_xpath
        )

        # with Modules Menu to be grid should render root menu w/ style=grid and render module w/o style=grid
        factory.app.use_grid_menus = True
        suite = factory.app.create_suite()
        self.assertXmlPartialEqual(
            '<partial><menu id="root" style="grid"><text/></menu></partial>',
            suite,
            root_xpath
        )
        self.assertXmlPartialEqual(
            '<partial><menu id="m0"><text><locale id="modules.m0"/></text><command id="m0-f0"/></menu></partial>',
            suite,
            m0_xpath
        )

    def test_grid_menu_for_some(self, *args):
        factory = AppFactory(build_version='2.24.3')
        factory.app.create_profile()
        factory.app.grid_form_menus = 'some'
        factory.new_basic_module('registration', 'patient')
        factory.new_basic_module('visit', 'patient visit')
        factory.app.get_module(1).display_style = 'grid'
        root_xpath = './menu[@id="root"]'
        grid_module_xpath = './menu[@id="m1"]'

        # with Modules Menu to be list should not render root menu and render module w/ style=grid
        factory.app.use_grid_menus = False
        suite = factory.app.create_suite()
        self.assertXmlDoesNotHaveXpath(suite, root_xpath)
        self.assertXmlHasXpath(suite, grid_module_xpath)
        self.assertXmlPartialEqual(
            '<partial><menu id="m1" style="grid"><text><locale id="modules.m1"/></text>\
            <command id="m1-f0"/></menu></partial>',
            suite,
            grid_module_xpath
        )

        # with Modules Menu to be grid should render both root menu and module w/ style=grid
        factory.app.use_grid_menus = True
        suite = factory.app.create_suite()
        self.assertXmlHasXpath(suite, root_xpath)
        self.assertXmlPartialEqual(
            '<partial><menu id="root" style="grid"><text/></menu></partial>',
            suite,
            root_xpath
        )
        self.assertXmlPartialEqual(
            '<partial><menu id="m1" style="grid"><text><locale id="modules.m1"/></text>\
            <command id="m1-f0"/></menu></partial>',
            suite,
            grid_module_xpath
        )

        # with module itself being the root should render root menu style=grid with module content
        factory.app.get_module(1).put_in_root = True
        suite = factory.app.create_suite()
        self.assertXmlPartialEqual(
            '<partial><menu id="root" style="grid"><text><locale id="modules.m1"/></text>\
            <command id="m1-f0"/></menu></partial>',
            suite,
            root_xpath
        )

    def test_grid_menu_for_all(self, *args):
        factory = AppFactory(build_version='2.24.3')
        factory.app.create_profile()
        factory.app.grid_form_menus = 'all'
        factory.new_basic_module('registration', 'patient')
        suite = factory.app.create_suite()
        root_xpath = './menu[@id="root"]'
        grid_module_xpath = './menu[@id="m0"]'

        # with Modules Menu to be list should not render root menu and render module w/ style=grid
        factory.app.use_grid_menus = False
        self.assertXmlDoesNotHaveXpath(suite, root_xpath)
        self.assertXmlPartialEqual(
            '<partial><menu id="m0" style="grid"><text><locale id="modules.m0"/></text>\
            <command id="m0-f0"/></menu></partial>',
            suite,
            grid_module_xpath
        )

        # with Modules Menu to be grid should render root menu and module w/ style=grid
        factory.app.use_grid_menus = True
        suite = factory.app.create_suite()
        self.assertXmlPartialEqual(
            '<partial><menu id="root" style="grid"><text/></menu></partial>',
            suite,
            root_xpath
        )
        self.assertXmlPartialEqual(
            '<partial><menu id="m0" style="grid"><text><locale id="modules.m0"/></text>\
            <command id="m0-f0"/></menu></partial>',
            suite,
            grid_module_xpath
        )

        # with Modules Menu to be list and module itself being the root should render root w/o style=grid with
        # module content
        factory.app.use_grid_menus = False
        factory.app.get_module(0).put_in_root = True
        suite = factory.app.create_suite()
        self.assertXmlPartialEqual(
            '<partial><menu id="root"><text><locale id="modules.m0"/></text>\
            <command id="m0-f0"/></menu></partial>',
            suite,
            root_xpath
        )

        # with Modules Menu to be grid and module itself being the root should render root w/ style=grid with
        # module content
        factory.app.get_module(0).put_in_root = True
        factory.app.use_grid_menus = True
        suite = factory.app.create_suite()
        self.assertXmlPartialEqual(
            '<partial><menu id="root" style="grid"><text><locale id="modules.m0"/></text>\
            <command id="m0-f0"/></menu></partial>',
            suite,
            root_xpath
        )
