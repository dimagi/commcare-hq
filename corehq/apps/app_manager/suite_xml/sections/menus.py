from corehq.apps.app_manager import id_strings
from corehq.apps.app_manager.exceptions import ScheduleError
from corehq.apps.app_manager.suite_xml.contributors import SuiteContributorByModule
from corehq.apps.app_manager.suite_xml.xml_models import Menu, Command, LocalizedMenu
from corehq.apps.app_manager.util import is_usercase_in_use
from corehq.apps.app_manager.xpath import interpolate_xpath, CaseIDXPath, session_var, QualifiedScheduleFormXPath
from corehq.feature_previews import MODULE_FILTER


class MenuContributor(SuiteContributorByModule):
    def get_module_contributions(self, module):
        def get_commands():
            for form in module.get_suite_forms():
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

                if (
                    getattr(form, 'form_filter', None) and
                    not module.put_in_root and
                    (module.all_forms_require_a_case() or is_usercase_in_use(self.app.domain))
                ):
                    fixture_xpath = (
                        session_var(id_strings.fixture_session_var(module)) if module.fixture_select.active
                        else None
                    )
                    command.relevant = interpolate_xpath(form.form_filter, case, fixture_xpath)

                if getattr(module, 'has_schedule', False) and module.all_forms_require_a_case():
                    # If there is a schedule and another filter condition, disregard it...
                    # Other forms of filtering are disabled in the UI

                    schedule_filter_condition = MenuContributor._schedule_filter_conditions(form, module, case)
                    if schedule_filter_condition is not None:
                        command.relevant = schedule_filter_condition

                yield command

            if hasattr(module, 'case_list') and module.case_list.show:
                yield Command(id=id_strings.case_list_command(module))

        supports_module_filter = (
            self.app.domain and MODULE_FILTER.enabled(self.app.domain) and
            self.app.enable_module_filtering and getattr(module, 'module_filter', None)
        )

        menus = []
        if hasattr(module, 'get_menus'):
            for menu in module.get_menus(supports_module_filter=supports_module_filter):
                menus.append(menu)
        elif module.module_type != 'careplan':
            id_modules = [module]
            root_modules = []

            shadow_modules = [m for m in self.app.get_modules()
                              if m.doc_type == "ShadowModule" and m.source_module_id]
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
                        suffix = id_strings.menu_id(root_module) if root_module.doc_type == 'ShadowModule' else ""
                    menu_kwargs.update({'id': id_strings.menu_id(id_module, suffix)})

                    if supports_module_filter:
                        menu_kwargs['relevant'] = interpolate_xpath(module.module_filter)

                    if self.app.enable_localized_menu_media:
                        menu_kwargs.update({
                            'menu_locale_id': id_strings.module_locale(module),
                            'media_image': bool(len(module.all_image_paths())),
                            'media_audio': bool(len(module.all_audio_paths())),
                            'image_locale_id': id_strings.module_icon_locale(module),
                            'audio_locale_id': id_strings.module_audio_locale(module),
                        })
                        menu = LocalizedMenu(**menu_kwargs)
                    else:
                        menu_kwargs.update({
                            'locale_id': id_strings.module_locale(module),
                            'media_image': module.default_media_image,
                            'media_audio': module.default_media_audio,
                        })
                        menu = Menu(**menu_kwargs)

                    menu.commands.extend(get_commands())

                    menus.append(menu)

        if self.app.use_grid_menus:
            self._give_root_menus_grid_style(menus)

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
    def _give_root_menus_grid_style(menus):
        for menu in menus:
            if menu.id == id_strings.ROOT:
                menu.style = "grid"
