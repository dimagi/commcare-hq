from abc import ABC, abstractmethod


class ArchiveWriter(ABC):
    """Writer used by ``dump_domain_data``."""

    path: str | None
    """Destination path, or ``None`` if no persisted artifact."""

    meta: dict
    """``{stream_name: {model: count}}``, accumulated as streams are written."""

    @abstractmethod
    def __contextmanager__(self):
        """Lifecycle generator wrapped by ``@contextmanager_class``."""

    @abstractmethod
    def open_stream(self, stream_name):
        """Yield a ``WrappedStream`` for writing; caller sets ``stream.meta``
        before the ``with`` block exits.
        """


class ArchiveReader(ABC):
    """Reader used by ``load_domain_data``."""

    path: str

    meta: dict
    """``{stream_name: {model: count}}`` from the archive's metadata."""

    @abstractmethod
    def __contextmanager__(self):
        """Lifecycle generator wrapped by ``@contextmanager_class``."""

    @abstractmethod
    def open_stream(self, stream_name):
        """Yield a ``WrappedStream`` for reading; ``stream.meta`` carries
        the per-stream metadata.
        """


class WrappedStream:
    """Per-call ``.meta`` carrier; isolates state across ``open_stream``
    calls for writers that reuse one underlying stream (e.g. stdout).
    """

    META_UNSET = object()

    def __init__(self, stream, meta=META_UNSET):
        self._stream = stream
        self.meta = meta

    def __getattr__(self, attr):
        return getattr(self._stream, attr)

    def __iter__(self):
        return iter(self._stream)
