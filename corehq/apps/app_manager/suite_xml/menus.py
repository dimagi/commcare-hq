from corehq.apps.app_manager import id_strings
from corehq.apps.app_manager.suite_xml.generator import SuiteContributorByModule
from corehq.apps.app_manager.suite_xml.xml_models import Menu, Command
from corehq.apps.app_manager.xform import SESSION_CASE_ID
from corehq.apps.app_manager.xpath import interpolate_xpath, CaseIDXPath, session_var
from corehq.feature_previews import MODULE_FILTER


class MenuContributor(SuiteContributorByModule):
    def get_module_contributions(self, module):
        # avoid circular dependency
        from corehq.apps.app_manager.models import AdvancedForm

        menus = []
        if hasattr(module, 'get_menus'):
            for menu in module.get_menus():
                menus.append(menu)
        elif module.module_type != 'careplan':
            menu_kwargs = {
                'id': id_strings.menu_id(module),
                'locale_id': id_strings.module_locale(module),
                'media_image': module.media_image,
                'media_audio': module.media_audio,
            }
            if id_strings.menu_root(module):
                menu_kwargs['root'] = id_strings.menu_root(module)

            if (self.app.domain and MODULE_FILTER.enabled(self.app.domain) and
                    self.app.enable_module_filtering and
                    getattr(module, 'module_filter', None)):
                menu_kwargs['relevant'] = interpolate_xpath(module.module_filter)

            menu = Menu(**menu_kwargs)

            def get_commands():
                for form in module.get_forms():
                    command = Command(id=id_strings.form_command(form))
                    if module.all_forms_require_a_case() and \
                            not module.put_in_root and \
                            getattr(form, 'form_filter', None):
                        if isinstance(form, AdvancedForm):
                            try:
                                action = next(a for a in form.actions.load_update_cases if not a.auto_select)
                                case = CaseIDXPath(session_var(action.case_session_var)).case() if action else None
                            except IndexError:
                                case = None
                        else:
                            case = SESSION_CASE_ID.case()

                        if case:
                            command.relevant = interpolate_xpath(form.form_filter, case)
                    yield command

                if hasattr(module, 'case_list') and module.case_list.show:
                    yield Command(id=id_strings.case_list_command(module))

            menu.commands.extend(get_commands())

            menus.append(menu)

        return menus
