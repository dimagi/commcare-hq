import json
import uuid
from datetime import datetime
from unittest.mock import patch

from django.core.cache import cache

from corehq.apps.celery import app as celery_app
from corehq.apps.export.export import get_export_file
from corehq.apps.export.tasks import build_export_schema
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


class StoreEagerCeleryResults:
    """Store eager Celery results so soil can read schema builds back

    Create and edit views poll a background schema build through soil,
    which reads the task's state from the result backend. Eager tasks
    are not stored there unless ``task_store_eager_result`` is set.
    Celery copies that setting to each task when the task is bound, so
    the task's own ``store_eager_result`` is set too.

    The cache is cleared before each test so that a build recorded by an
    earlier test (whose result was not stored) is not joined.

    List this mixin before ``TestCase`` in the bases, so that its
    ``setUp`` and ``setUpClass`` run. In the wrong order they are
    silently skipped.
    """

    def setUp(self):
        cache.clear()  # before super().setUp() logs in; sessions are cached
        super().setUp()

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        conf = celery_app.conf
        cls.addClassCleanup(setattr, conf, 'task_store_eager_result', conf.task_store_eager_result)
        conf.task_store_eager_result = True
        patcher = patch.object(build_export_schema, 'store_eager_result', True)
        patcher.start()
        cls.addClassCleanup(patcher.stop)
