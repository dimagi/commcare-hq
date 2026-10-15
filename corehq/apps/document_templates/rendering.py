"""
Renders the US letter template for the document template editor.
"""
from pathlib import Path

from jinja2 import Environment, meta, nodes

US_LETTER_TEMPLATE = Path(__file__).parent / 'static' / 'document_templates' / 'us_letter.html.j2'


def get_variable_names():
    return parse_variable_names(US_LETTER_TEMPLATE.read_text())


def parse_variable_names(source):
    """Names a Jinja template reads but does not define itself, in order of first use"""
    ast = Environment().parse(source)
    undeclared = meta.find_undeclared_variables(ast)
    used = (node.name for node in ast.find_all(nodes.Name))
    return [name for name in dict.fromkeys(used) if name in undeclared]
