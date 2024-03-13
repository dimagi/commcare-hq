from subprocess import Popen, PIPE
import os
import itertools
import logging


def shell_exec(cmd, cwd=None):
    """helper function to execute a command. returns stdout a la readlines().
    if any error occurs (exception, error return code), error is logged and
    None is returned. stderr is logged even if no error.

    cmd -- command to execute (will be passed to shell)
    cwd -- working directory in which to run command

    note: common directories will be automatically added to the syspath"""
    try:
        return shell_exec_checked(cmd, cwd)
    except ShellCommandError:
        logging.exception('error executing command [%s]' % cmd)
        return None


def shell_exec_checked(cmd, cwd=None):
    """execute a command, raising a ShellCommandError if any error occurs.
    return stdout otherwise. stderr is logged if no error occurs."""
    try:
        retcode, out, err = shell_exec_raw(cmd, cwd)
    except Exception as e:
        #not terribly sure what exceptions can occur when executing via shell.
        #maybe if the shell itself is missing. playing it safe anyway...
        raise ShellCommandError(ex=e)

    if retcode != 0:
        raise ShellCommandError(**locals())

    if err:
        logging.warning('command [%s] returned error output %s (return code OK)' % (cmd, str(err)))
    return out


def shell_exec_raw(cmd, cwd):
    """execute a command at a low level. returns (returncode, stdout, stderr).
    re-raises any exceptions"""
    def process_output(raw):
        output = raw.split('\n')
        if not output[-1]:
            del output[-1]
        return output

    p = Popen(cmd, stdout=PIPE, stderr=PIPE, shell=True, cwd=cwd, env=make_env())
    out, err = [process_output(data) for data in p.communicate()]
    return (p.returncode, out, err)


class ShellCommandError(Exception):
    """trap all the data resulting from running a shell process, in case there's an error"""

    def __init__(self, **kwargs):
        for var in ('ex', 'retcode', 'err', 'out'):
            setattr(self, var, kwargs.get(var))

    def __str__(self):
        if self.ex:
            return 'exception occured while executing subprocess: %s %s' % (type(self.ex), str(self.ex))
        else:
            return 'subprocess returned failure [%d], error output: %s' % (self.retcode, self.err)

    def __repr__(self):
        return '<ShellCommandError: %s>' % str(self)


def make_env():
    env = os.environ
    env['PATH'] = fix_path(env.get('PATH', ''))
    return env


def fix_path(path, pathext=[]):
    """add common directories to the syspath if missing. return path
    unchanged for non-unix systems"""
    OSINFO = {
        'posix': {
            'required_path': [
                '/usr/local/sbin',
                '/usr/local/bin',
                '/usr/sbin',
                '/usr/bin',
                '/sbin',
                '/bin',
            ],
            'path_sep': ':'
        }
    }

    if os.name not in OSINFO:
        return path

    pathsep = OSINFO[os.name]['path_sep']
    pathreq = OSINFO[os.name]['required_path']

    paths = [p for p in path.split(pathsep) if p]
    for rp in itertools.chain(pathext, pathreq):
        if rp not in paths:
            paths.append(rp)
    return pathsep.join(paths)
