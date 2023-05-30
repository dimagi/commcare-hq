..
    Documentation for evaluator functions. The order should be alphabetical.

.. py:function:: context()

    Get the current evaluation context.
    See also :func:`root_context`.

.. py:function:: date(value, fmt=None)

    Parse a string value as a date or timestamp. If ``fmt`` is not supplied
    the string is assumed to be in `ISO 8601`_ format.

    :param fmt: If supplied, use this format specification to parse the date.
                See the Python documentation for `Format Codes`_.

.. _ISO 8601: https://www.cl.cam.ac.uk/~mgk25/iso-time.html
.. _Format Codes: https://docs.python.org/3/library/datetime.html#strftime-and-strptime-format-codes

.. py:function:: float(value)

    Convert ``value`` to a floating point number.

.. py:function:: int(value)

    Convert ``value`` to an int. Value can be a number or
    a string representation of a number.

.. py:function:: jsonpath(expr, as_list=False, context=None)

    Evaluate a jsonpath expression.

    See also `Jsonpath Expression`_.

    .. code-block::

        jsonpath("form.case.name")
        jsonpath("name", context=jsonpath("form.case"))
        jsonpath("form..case", as_list=True)

    :param expr: The jsonpath expression.
    :param as_list: When set to True, always return the full list of matches, even if it is emtpy.
                    If set to False then the return value will be `None` if no matches are found.
                    If a single match is found the matched value will be returned.
                    If more than one match is found, they will all be returned as a list.
    :param context: Optional context for evaluation. If not supplied the full context of the evaluator
                    will be used.
    :return: See `as_list`.

.. py:function:: named(name, context=None)

    Call a named expression.
    See also `Named Expressions`_.

    .. code-block::

        named("my-named-expression")
        named("my-named-expression", context=form.case)

.. py:function:: rand()

    Generate a random number between 0 and 1

.. py:function:: randint(max)

    Generate a random integer between 0 and ``max``

.. py:function:: range(start, [stop], [skip])

    Produces a sequence of integers from start (inclusive) to stop (exclusive) by step.
    Note that for performance reasons this is limited to 100 items or less.
    See `range`_.

.. _range: https://docs.python.org/3/library/functions.html?#range

.. py:function:: root_context()

    Get the root context of the evaluation. Similar to the ``root_doc`` expression.

    See also :func:`context`.

.. py:function:: round(value, ndigits=None)

    Round a number to the nearest integer or ``ndigits``
    after the decimal point. See `round`_.

.. _round: https://docs.python.org/3/library/functions.html?#round

.. py:function:: str(value)

    Convert ``value`` to a string.

.. py:function:: timedelta_to_seconds(delta)

    Convert a TimeDelta object into seconds.
    This is useful for getting the number of seconds between two dates.

    .. code-block::

        timedelta_to_seconds(time_end - time_start)

.. py:function:: today()

    Return the current UTC date.
