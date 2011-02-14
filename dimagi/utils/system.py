from __future__ import absolute_import

from subprocess import Popen, PIPE
import os
import itertools
import logging

def shell_exec(cmd, cwd=None):
    """helper function to execute a command. returns stdout a la readlines().
    traps all exceptions. any stderr is logged, but not returned"""
    def process_output(raw):
        output = raw.split('\n')
        if not output[-1]:
            del output[-1]
        return output

    try:
        p = Popen(cmd, stdout=PIPE, stderr=PIPE, shell=True, cwd=cwd, env=make_env())
        (out, err) = [process_output(data) for data in p.communicate()]
        if err:
            logging.warn('command [%s] returned error output [%s]' % (cmd, str(err)))
        return out
    except:
        #not sure exception can be thrown when executing via shell; playing it safe...
        logging.exception('exception executing [%s]' % cmd)
        return None

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
