import os
import warnings


def configure_warnings(is_testing):
    if is_testing and 'PYTHONWARNINGS' not in os.environ:
        warnings.simplefilter("error")
