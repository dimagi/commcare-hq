import ast
import inspect
import os
from django.utils import importlib
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Lint tests"
    args = ""
    label = ""

    def handle(self, *args, **options):
        errors = []
        for module_path, class_name in parse_stdin():
            module = importlib.import_module(module_path)
            test_class = getattr(module, class_name)
            module_filepath = os.path.join(os.path.dirname(module.__file__),
                                           module_path.rsplit('.', 1)[1] + '.py')

            if 'setUpClass' in test_class.__dict__:
                class_node, = ast.parse(inspect.getsource(test_class)).body
                for node in ast.iter_child_nodes(class_node):
                    if isinstance(node, ast.FunctionDef) and node.name == 'setUpClass':
                        first_statement = list(ast.iter_child_nodes(node))[1]
                        if ast.dump(first_statement) != ast.dump(ast.Expr(
                            value=ast.Call(
                                func=ast.Attribute(
                                    value=ast.Call(
                                        func=ast.Name(id='super', ctx=ast.Load()),
                                        args=[
                                            ast.Name(id=class_name, ctx=ast.Load()),
                                            ast.Name(id='cls', ctx=ast.Load())],
                                        keywords=[],
                                        starargs=None,
                                        kwargs=None
                                    ),
                                    attr='setUpClass',
                                    ctx=ast.Load()
                                ),
                                args=[],
                                keywords=[],
                                starargs=None,
                                kwargs=None
                            )
                        )):
                            errors.append(
                                SetUpClassWithoutSuperCallMessage(module_filepath, test_class.setUpClass.func_code.co_firstlineno)
                            )
        if errors:
            for error in errors:
                print error
            exit(1)


class Message(object):
    message = None

    def __init__(self, filename, lineno):
        self.filename = filename
        self.lineno = lineno

    def __str__(self):
        # meant to mimic pyflakes format
        return '{}:{}: {}'.format(self.filename, self.lineno, self.message)


class SetUpClassWithoutSuperCallMessage(Message):
    message = 'setUpClass called without super call'


def parse_stdin():
    tests = set()
    import sys
    for line in sys.stdin:
        if ':' in line:
            module_path, rest = line.split(':', 1)
            class_name, _ = rest.split('.', 1)
            tests.add((module_path, class_name))
    for module_path, class_name in tests:
        yield module_path, class_name
