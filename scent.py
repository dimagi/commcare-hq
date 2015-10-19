import os
from subprocess import call

from sniffer.api import file_validator, runnable, select_runnable


@select_runnable('execute_tests')
@file_validator
def py_files(filename):
    return (filename.endswith('.py') or filename.endswith('.json')
            and not os.path.basename(filename).startswith('.'))


@runnable
def execute_tests(*args):
    fn = ['python', 'manage.py', 'test', '--noinput']
    fn += args[1:]
    return call(fn) == 0
