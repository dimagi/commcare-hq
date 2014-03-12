import os
import sh
import sys


def format_cwd(cwd):
    return os.path.join(cwd) if cwd else '.'


_original_init = sh.RunningCommand.__init__


def _verbose_init(self, cmd, call_args, stdin, stdout, stderr):
    print u"[{cwd}]$ {command}".format(
        cwd=format_cwd(call_args['cwd']),
        command=' '.join(cmd[0].rsplit('/', 1)[1:] + cmd[1:]),
    )
    try:
        _original_init(self, cmd, call_args, stdin, stdout, stderr)
    except sh.ErrorReturnCode as e:
        sys.stdout.write(e.stdout)
        sys.stderr.write(e.stderr)
        raise
    else:
        sys.stdout.write(self.stdout)
        sys.stderr.write(self.stderr)


def patch_sh_verbose():
    sh.RunningCommand.__init__ = _verbose_init


class ShVerbose(object):
    def __init__(self, verbose=True):
        self.verbose = verbose
        self.start_init = None

    def __enter__(self):
        # record whatever the current __init__ is so we can reset it later
        self.start_init = sh.RunningCommand.__init__
        sh.RunningCommand.__init__ = (_verbose_init if self.verbose
                                      else _original_init)

    def __exit__(self, exc_type, exc_val, exc_tb):
        sh.RunningCommand.__init__ = self.start_init
