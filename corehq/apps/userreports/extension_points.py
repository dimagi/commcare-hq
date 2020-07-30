from typing import List

from corehq.extensions import extension_point


@extension_point(flatten_results=True)
def static_ucr_data_source_paths() -> List[str]:
    """Pass additional paths to static UCR data sources.

    Parameters:
        None

    Returns:
        List of paths or globs to the static data source definition files
    """


@extension_point(flatten_results=True)
def static_ucr_reports() -> List[str]:
    """Pass additional paths to static UCR reports.

    Parameters:
        None

    Returns:
        List of paths or globs to the static report definition files
    """
