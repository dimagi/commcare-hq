from django.utils.translation import ugettext as _

from corehq.apps.es import filters

from .exceptions import XPathFunctionException


def _not(domain, node, fuzzy):
    from corehq.apps.case_search.filter_dsl import build_filter_from_ast

    if len(node.args) != 1:
        raise XPathFunctionException(_("The \"not\" function only accepts a single argument"))
    return filters.NOT(build_filter_from_ast(domain, node.args[0], fuzzy))
