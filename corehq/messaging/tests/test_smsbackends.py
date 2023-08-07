from unittest.mock import patch

from corehq.apps.hqadmin.management.commands import verify_ssl_connections


def test_iter_sms_endpoints():
    class ConsoleChecker:
        class style:
            WARNING = "WARNING"

        def console(message, style):
            assert style == ConsoleChecker.style.WARNING, (style, message)
            raise AssertionError(f"backend does not support SSL verification: {message}")

    Command = verify_ssl_connections.Command
    with patch.object(verify_ssl_connections, "iter_sms_urls", lambda *a: []):
        assert not list(Command.iter_sms_endpoints(ConsoleChecker))


def test_sms_urls():
    def test_manager(model_class):
        class NoDbManager:
            def filter(**kw):
                return [model_class()]
        return NoDbManager

    def test(model_class):
        def log(msg):
            raise NotImplementedError
        with patch.object(model_class, "active_objects", test_manager(model_class)):
            urls = list(verify_ssl_connections.iter_sms_urls(model_class, log))
            assert urls, f"{model_class} has no URL(s)"

    for name, model_class in verify_ssl_connections.iter_sms_model_classes():
        yield test, model_class
