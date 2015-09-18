from corehq.apps.app_manager import id_strings
from corehq.apps.app_manager.const import CAREPLAN_GOAL, CAREPLAN_TASK
from corehq.apps.app_manager.suite_xml.generator import SuiteContributor
from corehq.apps.app_manager.suite_xml.xml_models import Menu, Command


class CareplanContributor(SuiteContributor):
    section = 'menus'

    def contribute(self):
        self.suite.menus.extend(self.menus)

    @property
    def menus(self):
        # avoid circular dependency
        from corehq.apps.app_manager.models import CareplanModule

        menus = []
        for module in self.modules:
            if isinstance(module, CareplanModule):
                update_menu = Menu(
                    id=id_strings.menu_id(module),
                    locale_id=id_strings.module_locale(module),
                )

                if not module.display_separately:
                    parent = self.app.get_module_by_unique_id(module.parent_select.module_id)
                    create_goal_form = module.get_form_by_type(CAREPLAN_GOAL, 'create')
                    create_menu = Menu(
                        id=id_strings.menu_id(parent),
                        locale_id=id_strings.module_locale(parent),
                    )
                    create_menu.commands.append(Command(id=id_strings.form_command(create_goal_form)))
                    menus.append(create_menu)

                    update_menu.root = id_strings.menu_id(parent)
                else:
                    update_menu.commands.extend([
                        Command(id=id_strings.form_command(module.get_form_by_type(CAREPLAN_GOAL, 'create'))),
                    ])

                update_menu.commands.extend([
                    Command(id=id_strings.form_command(module.get_form_by_type(CAREPLAN_GOAL, 'update'))),
                    Command(id=id_strings.form_command(module.get_form_by_type(CAREPLAN_TASK, 'create'))),
                    Command(id=id_strings.form_command(module.get_form_by_type(CAREPLAN_TASK, 'update'))),
                ])
                menus.append(update_menu)
        return menus
