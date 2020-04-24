import os

import mock
from deployment.gunicorn.gunicorn_conf import _child_exit, _on_starting
from testil import eq


class Logger:
    def __init__(self):
        self.logs = []

    def exception(self, *args, **kwargs):
        self.logs.append((args, kwargs))


class Server:
    def __init__(self):
        self.log = Logger()


def setup():
    # ensure env var not set
    os.environ.pop('prometheus_multiproc_dir', None)


def test_on_starting():
    paths = [
        None,
        '',
        '/not/a/real/path',
    ]

    def _test(path):
        _on_starting(Server(), path=path)

    for path in paths:
        yield _test, path


def test_on_starting_error():
    server = Server()
    with mock.patch('deployment.gunicorn.gunicorn_conf._remove_prometheus_metric_files', side_effect=Exception):
        _on_starting(server, path='anything')

    eq(len(server.log.logs), 1)


def test_child_exit():
    server = Server()
    with mock.patch('deployment.gunicorn.gunicorn_conf._remove_prometheus_metric_files', side_effect=Exception):
        _child_exit(server, None, path='anything')

    eq(len(server.log.logs), 1)
