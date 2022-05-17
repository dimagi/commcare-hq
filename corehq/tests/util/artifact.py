import os
import logging
from contextlib import contextmanager

logger = logging.getLogger(__name__)

ROOT_ARTIFACTS_DIR = "artifacts"


@contextmanager
def artifact(filename, stream, mode="b", sub_name=None):
    """Context manager for writing artifact files on failure/error.

    :param filename: name of the artifact file to write.
    :param stream: file-like object used to read artifact contents
    :param mode: (optional) mode for opening artifact file (default=``b``, use
        ``t`` to open in text-write mode)
    :param sub_name: (optional) write the artifact file in a sub-directory
    """
    try:
        yield
    except Exception:
        artifact_dir = ROOT_ARTIFACTS_DIR
        if not os.path.exists(artifact_dir):
            # create the root artifacts directory (in the CWD)
            os.mkdir(artifact_dir)
        if sub_name:
            artifact_dir = os.path.join(artifact_dir, sub_name)
            if not os.path.exists(artifact_dir):
                os.mkdir(artifact_dir)
        artifact_path = os.path.join(artifact_dir, filename)
        logger.info(f"writing artifact: {artifact_path}")
        with open(artifact_path, f"w{mode}") as file:
            file.write(stream.read())
        raise
