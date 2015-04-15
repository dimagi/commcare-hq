from corehq.apps.app_manager.management.commands.helpers import AppMigrationCommandBase
from corehq.apps.app_manager.models import Application


class Command(AppMigrationCommandBase):
    help = "Migrate all graph configuration 'x-label-count' and " \
           "'y-label-count' properties to 'x-labels' and 'y-labels'"

    include_builds = True

    def migrate_app(self, app_doc):
        app = Application.wrap(app_doc)
        needs_save = False
        for module in app.get_modules():
            for detail_type in ["case_details", "task_details", "goal_details", "product_details"]:
                details = getattr(module, detail_type, None)
                if details is None:
                    # This module does not have the given detail_type
                    continue
                for detail in [details.short, details.long]:
                    for column in detail.get_columns():
                        graph_config = getattr(getattr(column, "graph_configuration", None), "config", {})
                        for axis in ["x", "y"]:
                            old_property = axis + "-label-count"
                            new_property = axis + "-labels"
                            count = graph_config.get(old_property, None)
                            if count is not None:
                                graph_config[new_property] = count
                                del graph_config[old_property]
                                needs_save = True

        return app if needs_save else None
