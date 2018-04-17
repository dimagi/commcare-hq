from __future__ import absolute_import
from __future__ import unicode_literals
from corehq import toggles
from corehq.apps.app_manager.const import USERCASE_TYPE
from corehq.apps.app_manager.util import is_usercase_in_use


def get_session_schema(form):
    """Get form session schema definition
    """
    from corehq.apps.app_manager.suite_xml.sections.entries import EntriesHelper
    app = form.get_app()
    structure = {}
    datums = EntriesHelper(app).get_datums_meta_for_form_generic(form)
    datums = [
        d for d in datums
        if not d.is_new_case_id and d.case_type and d.requires_selection
    ]
    if len(datums):
        session_var = datums[-1].datum.id
        structure["data"] = {
            "merge": True,
            "structure": {
                session_var: {
                    "reference": {
                        "hashtag": "#case",
                        "source": "casedb",
                        "subset": "case",
                        "key": "@case_id",
                    },
                },
            },
        }
    if is_usercase_in_use(app.domain):
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
