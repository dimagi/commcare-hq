"""Usage:
sniffer -x --js-app_manager -x corehq.apps.app_manager:AppManagerViewTest

You can get sniffer to run both js and python tests. Set which js tests you want to run with `--js-{app_name}`
Use the nose syntax for python tests
When you save a .js file, the js tests run,
When you save a .py file, the python tests run.
"""
from __future__ import absolute_import
from __future__ import unicode_literals
import os
from subprocess import Popen
from sniffer.api import runnable, select_runnable, file_validator


@select_runnable('python_tests')
@file_validator
def python_test_files(filename):
    return (
        (filename.endswith('.py') or
         filename.endswith('.json') or
         filename.endswith('.xml'))
        and not os.path.basename(filename).startswith('.')
    )


# Here we instruct the 'javascript_tests' runnable to be kicked off
# when a .js file is changed
@select_runnable('javascript_tests')
@file_validator
def js_files(filename):
    return filename.endswith('.js') and not os.path.basename(filename).startswith('.')


def run_test(fn):
    process = Popen(fn)
    try:
        return process.wait() == 0
    except KeyboardInterrupt:
        process.terminate()
        raise


@runnable
def javascript_tests(*args):
    fn = ['grunt']
    args = args[1:]
    tests_to_run = ["mocha:{}".format(arg.split('--js-')[1]) for arg in args if arg.startswith('--js-')]

    if tests_to_run:
        fn += tests_to_run
        return run_test(fn)
    return True


@runnable
def python_tests(*args):
    fn = ['python', 'manage.py', 'test', '--noinput', '--settings=testsettings']
    args = args[1:]
    tests_to_run = [arg for arg in args if not arg.startswith('--js-')]

    if tests_to_run:
        fn += tests_to_run
        return run_test(fn)

    return True
