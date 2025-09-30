from django.utils.text import slugify

from corehq.apps.app_manager.const import USERCASE_TYPE
from corehq.apps.app_manager.suite_xml.xml_models import InstanceDatum
from corehq.apps.app_manager.templatetags.xforms_extras import clean_trans
from corehq.apps.app_manager.util import domain_has_usercase_access


def get_session_schema(form):
    """Get form session schema definition
    """
    from corehq.apps.app_manager.suite_xml.sections.entries import EntriesHelper
    app = form.get_app()
    structure = {}
    datums = EntriesHelper(app).get_case_datums_meta_for_form(form)
    datums = [d for d in datums if not d.is_new_case_id]

    def _get_structure(datum, data_registry, source=None):
        id_source = f":{slugify(source)}" if source else ""
        return {
            "reference": {
                "hashtag": f'#registry_case{id_source}' if data_registry else f"#case{id_source}",
                "source": "registry" if data_registry else "casedb",
                "subset": f"case{id_source}",
                "key": "@case_id",
            },
        }

    unrelated_parents = set()
    for datum in datums:
        if not datum.module_id:
            continue
        module = app.get_module_by_unique_id(datum.module_id)
        parent_select_active = hasattr(module, 'parent_select') and module.parent_select.active
        if parent_select_active and module.parent_select.relationship is None:
            # for child modules that use parent select where the parent is not a 'related' case
            # See toggles.NON_PARENT_MENU_SELECTION
            unrelated_parents.add(module.parent_select.module_id)

    data_structure = {}
    for i, datum in enumerate(reversed(datums)):
        if isinstance(datum.datum, InstanceDatum):
            continue
        module_id = datum.module_id
        module = app.get_module_by_unique_id(module_id) if module_id else None
        data_registry = module.search_config.data_registry if module else None
        if i == 0:
            # always add the datum for this module
            data_structure[datum.id] = _get_structure(datum, data_registry)
        else:
            if module and module_id in unrelated_parents:
                source = clean_trans(module.name, app.langs)  # ensure that this structure reference is unique
                data_structure[datum.id] = _get_structure(datum, data_registry, source)

    if data_structure:
        structure["data"] = {
            "merge": True,
            "structure": data_structure,
        }

    if domain_has_usercase_access(app.domain):
        structure["context"] = {
            "merge": True,
            "structure": {
                "userid": {
                    "reference": {
                        "hashtag": "#user",
                        "source": "casedb",
                        "subset": USERCASE_TYPE,
                        "subset_key": "@case_type",
                        "subset_filter": True,
                        "key": "hq_user_id",
                    },
                },
            },
        }
    return {
        "id": "commcaresession",
        "uri": "jr://instance/session",
        "name": "Session",
        "path": "/session",
        "structure": structure,
    }
