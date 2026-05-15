from contextlib import contextmanager


def contextmanager_class(cls):
    """Enable ``with cls():`` semantics based on ``cls``'s
    ``__contextmanager__`` method, which must be of the form expected
    by ``@contextmanager``.
    """
    cls.__contextmanager__ = contextmanager(cls.__contextmanager__)

    def __enter__(self):
        self._cm = self.__contextmanager__()
        return self._cm.__enter__()

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            return self._cm.__exit__(exc_type, exc_val, exc_tb)
        finally:
            self._cm = None

    cls.__enter__ = __enter__
    cls.__exit__ = __exit__
    return cls


def get_tmp_extract_dir(dump_file_path, specifier=""):
    return f'_tmp_load_{specifier}_{dump_file_path}'
