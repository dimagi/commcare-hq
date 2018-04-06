from __future__ import absolute_import
from __future__ import unicode_literals
from corehq.apps.app_manager import id_strings
from corehq.apps.app_manager.exceptions import (ScheduleError, CaseXPathValidationError,
    UserCaseXPathValidationError)
from corehq.apps.app_manager.suite_xml.contributors import SuiteContributorByModule
from corehq.apps.app_manager.suite_xml.xml_models import Menu, Command, LocalizedMenu
from corehq.apps.app_manager.util import (is_usercase_in_use, xpath_references_case,
    xpath_references_user_case)
from corehq.apps.app_manager.xpath import (interpolate_xpath, CaseIDXPath, session_var,
    QualifiedScheduleFormXPath)
from memoized import memoized


class MenuContributor(SuiteContributorByModule):

    def get_module_contributions(self, module):
        def get_commands(excluded_form_ids):
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
                    form_datums = self.entries_helper.get_datums_meta_for_form_generic(form, module)
                    var_name = next(
                        meta.datum.id for meta in reversed(form_datums)
                        if meta.action and meta.requires_selection
                    )
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

                    if xpath_references_user_case(interpolated_xpath) and not domain_uses_usercase():
                        raise UserCaseXPathValidationError(module=module, form=form)

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

        supports_module_filter = self.app.enable_module_filtering and getattr(module, 'module_filter', None)

        menus = []
        if hasattr(module, 'get_menus'):
            for menu in module.get_menus(supports_module_filter=supports_module_filter):
                menus.append(menu)
        else:
            from corehq.apps.app_manager.models import ShadowModule
            id_modules = [module]
            root_modules = []

            shadow_modules = [m for m in self.app.get_modules()
                              if isinstance(m, ShadowModule) and m.source_module_id]
            put_in_root = getattr(module, 'put_in_root', False)
            if not put_in_root and getattr(module, 'root_module', False):
                root_modules.append(module.root_module)
                for shadow in shadow_modules:
                    if module.root_module.unique_id == shadow.source_module_id:
                        root_modules.append(shadow)
            else:
                root_modules.append(None)
                if put_in_root and getattr(module, 'root_module', False):
                    for shadow in shadow_modules:
                        if module.root_module.unique_id == shadow.source_module_id:
                            id_modules.append(shadow)

            for id_module in id_modules:
                for root_module in root_modules:
                    menu_kwargs = {}
                    suffix = ""
                    if root_module:
                        menu_kwargs.update({'root': id_strings.menu_id(root_module)})
                        suffix = id_strings.menu_id(root_module) if isinstance(root_module, ShadowModule) else ""
                    menu_kwargs.update({'id': id_strings.menu_id(id_module, suffix)})

                    if supports_module_filter:
                        menu_kwargs['relevant'] = interpolate_xpath(module.module_filter)

                    if self.app.enable_localized_menu_media:
                        module_custom_icon = module.custom_icon
                        menu_kwargs.update({
                            'menu_locale_id': id_strings.module_locale(module),
                            'media_image': bool(len(module.all_image_paths())),
                            'media_audio': bool(len(module.all_audio_paths())),
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
                            'locale_id': id_strings.module_locale(module),
                            'media_image': module.default_media_image,
                            'media_audio': module.default_media_audio,
                        })
                        menu = Menu(**menu_kwargs)

                    excluded_form_ids = []
                    if root_module and isinstance(root_module, ShadowModule):
                        excluded_form_ids = root_module.excluded_form_ids
                    if id_module and isinstance(id_module, ShadowModule):
                        excluded_form_ids = id_module.excluded_form_ids
                    menu.commands.extend(get_commands(excluded_form_ids))

                    if len(menu.commands):
                        menus.append(menu)

        if self.app.grid_display_for_all_modules() or \
                self.app.grid_display_for_some_modules() and module.grid_display_style():
            self._give_non_root_menus_grid_style(menus)
        if self.app.use_grid_menus:
            self._give_root_menu_grid_style(menus)

        return menus

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
