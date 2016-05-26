from subprocess import Popen
from sniffer.api import runnable


@runnable
def execute_tests(*args):
    fn = ['python', 'manage.py', 'test', '--noinput', '--settings=testsettings']
    fn += args[1:]
    process = Popen(fn)
    try:
        return process.wait() == 0
    except KeyboardInterrupt:
        process.terminate()
        raise
