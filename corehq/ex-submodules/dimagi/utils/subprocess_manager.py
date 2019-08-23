from __future__ import absolute_import
from __future__ import unicode_literals
import contextlib
import logging
import subprocess

logger = logging.getLogger(__name__)

try:
    from errand_boy.transports.unixsocket import UNIXSocketTransport
    @contextlib.contextmanager
    def subprocess_errand_boy():
        transport = UNIXSocketTransport()
        with transport.get_session() as session:
            yield session.subprocess

    @contextlib.contextmanager
    def subprocess_context():
        in_context = False
        try:
            with subprocess_errand_boy() as remote_subprocess:
                in_context = True
                yield remote_subprocess
        except IOError:
            if in_context:
                raise
            logger.exception("Unable to communicate with errand boy, falling back to subprocess")
            yield subprocess

except ImportError:
    @contextlib.contextmanager
    def subprocess_context():
        yield subprocess
