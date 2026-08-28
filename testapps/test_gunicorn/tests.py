from unittest import mock

from unmagic import fixture, use

from deployment.gunicorn.gunicorn_conf import (
    _mark_prometheus_worker_dead,
    _remove_prometheus_metric_files,
    child_exit,
    on_starting,
)

monkeypatch = fixture('monkeypatch')
tmp_path = fixture('tmp_path')


class Logger:
    def __init__(self):
        self.logs = []

    def exception(self, *args, **kwargs):
        self.logs.append((args, kwargs))


class Server:
    def __init__(self):
        self.log = Logger()


@use(tmp_path, monkeypatch)
@fixture
def prometheus_dir():
    """Point the prometheus directory at a temporary sandbox"""
    path = tmp_path()
    monkeypatch().setenv('PROMETHEUS_MULTIPROC_DIR', str(path))
    yield path


@use(prometheus_dir)
def test_remove_prometheus_metric_files_deletes_metric_files():
    path = prometheus_dir()
    (path / 'counter_1.db').touch()
    (path / 'not-metrics-file.txt').touch()

    _remove_prometheus_metric_files()

    assert [f.name for f in path.iterdir()] == ['not-metrics-file.txt']


@use(prometheus_dir)
def test_mark_prometheus_worker_dead():
    path = prometheus_dir()
    worker = mock.Mock(pid=4321)

    with mock.patch('prometheus_client.multiprocess.mark_process_dead') as mark_process_dead:
        _mark_prometheus_worker_dead(worker)

    mark_process_dead.assert_called_once_with(4321, str(path))


def test_on_starting_logs_errors():
    server = Server()
    with mock.patch('deployment.gunicorn.gunicorn_conf._remove_prometheus_metric_files', side_effect=Exception):
        on_starting(server)

    assert len(server.log.logs) == 1


def test_child_exit_logs_errors():
    server = Server()
    with mock.patch('deployment.gunicorn.gunicorn_conf._remove_prometheus_metric_files', side_effect=Exception):
        child_exit(server, None)

    assert len(server.log.logs) == 1
