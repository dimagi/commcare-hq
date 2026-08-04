from corehq.extensions import extension_point, ResultFormat


@extension_point(result_format=ResultFormat.FLATTEN)
def static_ucr_data_source_paths():
    """Pass additional paths to static UCR data sources.

    Parameters:
        None

    Returns:
        List of paths or globs to the static data source definition files
    """


@extension_point(result_format=ResultFormat.FLATTEN)
def static_ucr_report_paths():
    """Pass additional paths to static UCR reports.

    Parameters:
        None

    Returns:
        List of paths or globs to the static report definition files
    """


@extension_point(result_format=ResultFormat.FLATTEN)
def custom_ucr_expressions():
    """Additional UCR expression functions

    Parameters:
        None

    Returns:
        List of Tuple[expression_name, python path to expression function]

        The function must take two arguments:

        * spec: Dict
        * factory_context: FactoryContext instance
    """


@extension_point(result_format=ResultFormat.FLATTEN)
def custom_ucr_report_filters():
    """Custom UCR report filter functions

    Parameters:
        None

    Returns:
        List of Tuple[filter_name, python path to filter function]

        The function must take two arguments:

        * spec: Dict
        * report: ReportConfiguration instance"""


@extension_point(result_format=ResultFormat.FLATTEN)
def custom_ucr_report_filter_values():
    """Custom filter values

    Parameters:
        None

    Returns:
        List of Tuple[value_name, python path to value class]

        The value class must extend ``ChoiceListFilterValue``
        """
