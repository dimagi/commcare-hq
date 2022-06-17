from django.utils.translation import gettext as _

from eulxml.xpath import serialize

from corehq.apps.case_search.exceptions import XPathFunctionException


def confirm_args_count(node, expected):
    actual = len(node.args)
    if actual != expected:
        raise XPathFunctionException(
            _(f"The '{node.name}' function accepts exactly {expected} arguments, got {actual}"),
            serialize(node)
        )
