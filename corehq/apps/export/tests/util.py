import json
import uuid
from datetime import datetime

from corehq.apps.export.export import get_export_file
from corehq.form_processor.models import CommCareCase
from corehq.form_processor.tests.utils import create_form_for_test
from corehq.util.files import TransientTempfile

DOMAIN = "export-file-domain"
DEFAULT_USER = "user1"
DEFAULT_CASE_TYPE = "test-case-type"
DEFAULT_CASE_NAME = "a case"
DEFAULT_APP_ID = "test-app-id"
DEFAULT_XMLNS = "test-xmlns"


def new_case(domain=DOMAIN, user_id=DEFAULT_USER, owner_id=DEFAULT_USER,
             type=DEFAULT_CASE_TYPE, name=DEFAULT_CASE_NAME,
             closed=False, **kwargs):
    kwargs.setdefault("case_id", uuid.uuid4().hex)
    kwargs.setdefault("modified_on", datetime.utcnow())
    kwargs.setdefault("server_modified_on", datetime.utcnow())
    return CommCareCase(
        domain=domain,
        user_id=user_id,
        owner_id=owner_id,
        type=type,
        name=name,
        closed=closed,
        **kwargs
    )


def new_form(form_data):
    return create_form_for_test(
        domain=DOMAIN,
        app_id=DEFAULT_APP_ID,
        xmlns=DEFAULT_XMLNS,
        form_data=form_data,
        save=False,
    )


def assertContainsExportItems(item_tuples, export_group_schema):
    """
    :param item_tuples: list of ("path", "label") tuples representing each export item:
    eg:  [("form.group.question2", "question_label")]
    """
    actual = {
        (item.readable_path, item.label)
        for item in export_group_schema.items
    }
    item_set = set(item_tuples)
    missing = item_set - actual
    extra = actual - item_set
    if missing or extra:
        def prettify(list_of_tuples):
            return '\n  '.join(map(str, list_of_tuples))
        raise AssertionError("Contains items:\n  {}\nMissing items:\n  {}\nExtra items:\n {}"
                             .format(prettify(actual), prettify(missing), prettify(extra)))


def get_export_json(export_instance):
    with TransientTempfile() as temp_path:
        export_file = get_export_file([export_instance], [], temp_path)

        with export_file as export:
            return json.loads(export.read())
