from unittest.mock import patch

from celery import current_app
from testil import assert_raises

from corehq.apps import celery as celery_app


def test_init_celery_app():
    app = getattr(celery_app, "app", None)
    assert app is not None, "Celery is not initialized"


def test_celery_always_eager():
    conf = celery_app.app.conf
    assert conf.task_always_eager, "task_always_eager is required for tests"


def test_celery_current_app():
    current = current_app._get_current_object()
    assert celery_app.app is current, (celery_app.app, current)


def test_current_app_pre_init_error():
    with patch("celery._state.default_app", None):
        with assert_raises(RuntimeError):
            current_app._get_current_object()
