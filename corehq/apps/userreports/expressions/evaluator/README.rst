.. py:function:: context()

    Get the current evaluation context.

.. py:function:: root_context()

    Get the root context of the evaluation.

.. py:function:: named(name, context=None)

    Call a named expression.

    .. code-block::

        named("my-named-expression")
        named("my-named-expression", context=form.case)


.. py:function:: jsonpath(expr, as_list=False, context=None)

    Evaluate a jsonpath expression.

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
