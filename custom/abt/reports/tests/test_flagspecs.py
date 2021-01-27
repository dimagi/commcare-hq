from glob import glob

from yaml import load, Loader, parser


def test_yaml_formatting():
    for filename in glob('custom/abt/reports/*.yaml'):
        yield check_yaml_file, filename


def check_yaml_file(filename):
    with open(filename, 'r') as f:
        try:
            load(f.read(), Loader=Loader)
        except parser.ParserError:
            assert False  # nose will tell us which file, and what went wrong.
