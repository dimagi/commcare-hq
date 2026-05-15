from contextlib import contextmanager

from .base import ArchiveWriter, WrappedStream
from .utils import contextmanager_class, validate_stream_meta


@contextmanager_class
class SimpleSingleStreamWriter(ArchiveWriter):

    path = None

    def __init__(self, output_stream):
        self.meta = {}
        self._output_stream = output_stream

    def __contextmanager__(self):
        yield self

    @contextmanager
    def open_stream(self, stream_name):
        # The underlying output_stream is intentionally NOT closed
        # between dumpers — it's owned by the caller (typically stdout).
        wrapped_stream = WrappedStream(self._output_stream)
        yield wrapped_stream
        validate_stream_meta(wrapped_stream, stream_name)
        self.meta[stream_name] = wrapped_stream.meta

    def __repr__(self):
        return f"<{type(self).__name__}>"
