"""
MenuContributor
---------------

Menus *approximately* correspond to HQ modules.

Menus *almost* correspond to command lists, the screens in CommCare that ask the user to select a form or sub-menu.
However, if the suite contains multiple ``<menu>`` elements with the same ``id``, they will be concatenated and
displayed as a single screen.

Menu ids will typically map to the module's position in the application: the first menu is ``m0``, second is
``m1``, etc.

Highlights of menu configuration:

* Display conditions, which become ``relevant`` attributes
* Display-only forms, which becomes the ``put_in_root`` attribute
* Grid style, to determine whether the  command list should be displayed as a flat list or as a grid that
  emphasizes the menu icons
"""
from memoized import memoized

from corehq.apps.app_manager import id_strings
from corehq.apps.app_manager.exceptions import (
    CaseXPathValidationError,
    ScheduleError,
    UsercaseXPathValidationError,
)
from corehq.apps.app_manager.suite_xml.contributors import (
    SuiteContributorByModule,
)
from corehq.apps.app_manager.suite_xml.sections.entries import EntriesHelper
from corehq.apps.app_manager.suite_xml.utils import get_module_locale_id
from corehq.apps.app_manager.suite_xml.xml_models import (
    Command,
    LocalizedMenu,
    Menu,
)
from corehq.apps.app_manager.util import (
    is_usercase_in_use,
    xpath_references_case,
    xpath_references_usercase,
)
from corehq.apps.app_manager.xpath import (
    CaseIDXPath,
    QualifiedScheduleFormXPath,
    XPath,
    interpolate_xpath,
    session_var,
)
from corehq.util.timer import time_method


class MenuContributor(SuiteContributorByModule):

    @time_method()
    def get_module_contributions(self, module, training_menu):
        menus = []
        if hasattr(module, 'get_menus'):
            for menu in module.get_menus(build_profile_id=self.build_profile_id):
                menus.append(menu)
        else:
            module_is_source_for_v1_shadow = any(
                m for m in self._v1_shadow_modules()
                if (m.source_module_id == module.unique_id)
                or (getattr(module, 'root_module', False)
                    and m.source_module_id == module.root_module.unique_id)
            )
            module_is_v1_shadow = getattr(module, 'shadow_module_version', 0) == 1

            if module_is_v1_shadow or module_is_source_for_v1_shadow:
                for v1_shadow_menu in self._generate_v1_shadow_menus(module, training_menu):
                    menus.append(v1_shadow_menu)
            else:
                root_module = None
                if not module.put_in_root:
                    if module.root_module:
                        root_module = module.root_module
                    elif module.module_type == 'shadow' and module.source_module.root_module:
                        root_module = module.source_module.root_module

                menu = self._generate_menu(module, root_module, training_menu, module)
                if len(menu.commands):
                    menus.append(menu)

        if self.app.grid_display_for_all_modules():
            self._give_non_root_menus_grid_style(menus)
        elif self.app.grid_display_for_some_modules():
            if hasattr(module, 'grid_display_style') and module.grid_display_style():
                self._give_non_root_menus_grid_style(menus)
        if self.app.use_grid_menus:
            self._give_root_menu_grid_style(menus)

        return menus

    @memoized
    def _v1_shadow_modules(self):
        return [
            m for m in self.app.get_modules()
            if m.module_type == 'shadow'
            and m.shadow_module_version == 1
            and m.source_module_id
        ]

    def _generate_v1_shadow_menus(self, module, training_menu):
        # V1 shadow modules create a 'fake' module for any child shadow menus
        # These child shadow modules don't have a representation in the DB, but
        # are needed in the suite to add in all the child forms.
        # This behaviour has been superceded by v2 shadow modules.

        id_modules = [module]       # the current module and all of its shadows
        root_modules = []           # the current module's parent and all of that parent's shadows

        if not module.put_in_root and module.root_module:
            root_modules.append(module.root_module)
            for shadow in self._v1_shadow_modules():
                if module.root_module.unique_id == shadow.source_module_id:
                    root_modules.append(shadow)
        else:
            root_modules.append(None)
            if module.put_in_root and module.root_module:
                for shadow in self._v1_shadow_modules():
                    if module.root_module.unique_id == shadow.source_module_id:
                        id_modules.append(shadow)

        for id_module in id_modules:
            for root_module in root_modules:
                menu = self._generate_menu(module, root_module, training_menu, id_module)
                if len(menu.commands):
                    yield menu

    def _generate_menu(self, module, root_module, training_menu, id_module):
        # In general, `id_module` and `module` will be the same thing.
        # In the case of v1 shadow menus, `id_module` is either the current module or one of that module's shadows
        # For more information, see the note in `_generate_v1_shadow_menus`.
        from corehq.apps.app_manager.models import ShadowModule
        menu_kwargs = {}
        suffix = ""
        if id_module.is_training_module:
            menu_kwargs.update({'root': 'training-root'})
        elif root_module:
            menu_kwargs.update({'root': id_strings.menu_id(root_module)})
            suffix = id_strings.menu_id(root_module) if isinstance(root_module, ShadowModule) else ""
        menu_kwargs.update({'id': id_strings.menu_id(id_module, suffix)})

        # Determine relevancy
        if self.app.enable_module_filtering:
            relevancy = id_module.module_filter
            # If module has a parent, incorporate the parent's relevancy.
            # This is only necessary when the child uses display only forms.
            if id_module.put_in_root and id_module.root_module and id_module.root_module.module_filter:
                if relevancy:
                    relevancy = str(XPath.and_(XPath(relevancy).paren(force=True),
                        XPath(id_module.root_module.module_filter).paren(force=True)))
                else:
                    relevancy = id_module.root_module.module_filter
            if relevancy:
                menu_kwargs['relevant'] = interpolate_xpath(relevancy)

        if self.app.enable_localized_menu_media:
            module_custom_icon = module.custom_icon
            menu_kwargs.update({
                'menu_locale_id': get_module_locale_id(module),
                'media_image': module.uses_image(build_profile_id=self.build_profile_id),
                'media_audio': module.uses_audio(build_profile_id=self.build_profile_id),
                'image_locale_id': id_strings.module_icon_locale(module),
                'audio_locale_id': id_strings.module_audio_locale(module),
                'custom_icon_locale_id': (
                    id_strings.module_custom_icon_locale(module, module_custom_icon.form)
                    if module_custom_icon and not module_custom_icon.xpath else None),
                'custom_icon_form': (module_custom_icon.form if module_custom_icon else None),
                'custom_icon_xpath': (module_custom_icon.xpath
                                      if module_custom_icon and module_custom_icon.xpath else None),
            })
            menu = LocalizedMenu(**menu_kwargs)
        else:
            menu_kwargs.update({
                'media_image': module.default_media_image,
                'media_audio': module.default_media_audio,
                'locale_id': get_module_locale_id(module),
            })
            menu = Menu(**menu_kwargs)

        excluded_form_ids = []
        if root_module and isinstance(root_module, ShadowModule):
            excluded_form_ids = root_module.excluded_form_ids
        if id_module and isinstance(id_module, ShadowModule):
            excluded_form_ids = id_module.excluded_form_ids

        commands = self._get_commands(excluded_form_ids, module)
        if module.is_training_module and module.put_in_root and training_menu:
            training_menu.commands.extend(commands)
        else:
            menu.commands.extend(commands)

        for id, assertion in enumerate(module.custom_assertions):
            menu.assertions.append(EntriesHelper.get_assertion(
                assertion.test,
                id_strings.custom_assertion_locale(id, module),
            ))

        return menu

    @staticmethod
    def _schedule_filter_conditions(form, module, case):
        phase = form.get_phase()
        try:
            form_xpath = QualifiedScheduleFormXPath(form, phase, module, case_xpath=case)
            relevant = form_xpath.filter_condition(phase.id)
        except ScheduleError:
            relevant = None
        return relevant

    @staticmethod
    def _give_non_root_menus_grid_style(menus):
        for menu in menus:
            if not menu.id == id_strings.ROOT:
                menu.style = "grid"

    @staticmethod
    def _give_root_menu_grid_style(menus):
        for menu in menus:
            if menu.id == id_strings.ROOT:
                menu.style = "grid"

    @staticmethod
    def _give_all_menus_grid_style(menus):
        for menu in menus:
            menu.style = "grid"

    def _get_commands(self, excluded_form_ids, module):
        @memoized
        def module_uses_case():
            return module.all_forms_require_a_case()

        @memoized
        def domain_uses_usercase():
            return is_usercase_in_use(self.app.domain)

        for form in module.get_suite_forms():
            if form.unique_id in excluded_form_ids:
                continue

            command = Command(id=id_strings.form_command(form, module))

            if form.requires_case():
                var_name = self.entries_helper.get_case_session_var_for_form(form)
                case = CaseIDXPath(session_var(var_name)).case()
            else:
                case = None

            if getattr(form, 'form_filter', None):
                fixture_xpath = (
                    session_var(id_strings.fixture_session_var(module)) if module.fixture_select.active
                    else None
                )
                interpolated_xpath = interpolate_xpath(form.form_filter, case, fixture_xpath,
                    module=module, form=form)

                if xpath_references_case(interpolated_xpath) and \
                        (not module_uses_case() or
                        module.put_in_root and not module.root_requires_same_case()):
                    raise CaseXPathValidationError(module=module, form=form)

                if xpath_references_usercase(interpolated_xpath) and not domain_uses_usercase():
                    raise UsercaseXPathValidationError(module=module, form=form)

                command.relevant = interpolated_xpath

            if getattr(module, 'has_schedule', False) and module.all_forms_require_a_case():
                # If there is a schedule and another filter condition, disregard it...
                # Other forms of filtering are disabled in the UI

                schedule_filter_condition = MenuContributor._schedule_filter_conditions(form, module, case)
                if schedule_filter_condition is not None:
                    command.relevant = schedule_filter_condition

            yield command

        if hasattr(module, 'case_list') and module.case_list.show:
            yield Command(id=id_strings.case_list_command(module))
