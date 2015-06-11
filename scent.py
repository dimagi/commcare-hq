from subprocess import call
from sniffer.api import runnable


@runnable
def execute_tests(*args):
    fn = ['python', 'manage.py', 'test', '--noinput']
    fn += args[1:]
    return call(fn) == 0
