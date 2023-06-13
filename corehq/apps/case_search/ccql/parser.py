from django.utils.functional import SimpleLazyObject
from lark import Lark

from .ast import CCQLTransformer

grammer_file = "ccql.lark"


def _make_parser():
    return Lark.open(grammer_file, rel_to=__file__, parser='lalr', transformer=CCQLTransformer())


parser = SimpleLazyObject(_make_parser)
