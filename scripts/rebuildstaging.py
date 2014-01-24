"""
This file is meant to be used in the following manner:

$ python make_rebuild_staging.py < staging.yaml [-v] [fetch] [sync] [check] [rebuild]

Where staging.yaml looks as follows:

    trunk: master
    name: autostaging
    branches:
      - feature1
      - feature2
    submodules:
      submodules/module1:
        branches:
          - feature1
      submodules/module2:
        trunk: develop
        branches:
          - feature2

When not specified, a submodule's trunk and name inherit from the parent
"""

import os
import jsonobject
import sh
import sys


def get_git(path=None):
    return sh.git.bake('--no-pager', _cwd=path)


def git_current_branch(git):
    return sh.grep(git.branch('--no-color'), '^* ').strip()[2:]


def git_check_merge(branch1, branch2, git):
    """
    returns True if branch1 would auto-merge cleanly into branch2,
    False if the merge requires human assistance

    Thanks to http://stackoverflow.com/a/501461/240553

    """
    with ShVerbose(False):
        orig_branch = git_current_branch(git)
        git.checkout(branch2)
        is_behind = git.log('{0}..{1}'.format(branch2, branch1),
                            max_count=1).strip()
        if is_behind:
            try:
                git.merge('--no-commit', '--no-ff', branch1).strip()
            except sh.ErrorReturnCode_1:
                # git merge returns 1 when there's a conflict
                return False
            else:
                return True
            finally:
                git.merge('--abort')
                git.checkout(orig_branch)
        else:
            return True

class BranchConfig(jsonobject.JsonObject):
    trunk = jsonobject.StringProperty()
    name = jsonobject.StringProperty()
    branches = jsonobject.ListProperty(unicode)
    submodules = jsonobject.DictProperty(lambda: BranchConfig)

    def normalize(self):
        for submodule, subconfig in self.submodules.items():
            subconfig.trunk = subconfig.trunk or self.trunk
            subconfig.name = subconfig.name or self.name

    def span_configs(self, path=('.',)):
        for submodule, subconfig in self.submodules.items():
            for item in subconfig.span_configs(path + (submodule,)):
                yield item
        yield os.path.join(*path), self


def fetch_remote(base_config):
    for path in set(path for path, _ in base_config.span_configs()):
        git = get_git(path)
        print "  [{cwd}] fetching all".format(cwd=path)
        git.fetch('--all')
    print "All branches fetched"


def sync_local_copies(config):
    base_config = config
    unpushed_branches = []

    def _count_commits(compare_spec):
        return int(sh.wc(git.log(compare_spec, '--oneline', _piped=True), '-l'))

    for path, config in base_config.span_configs():
        git = get_git(path)

        for branch in [config.trunk] + config.branches:
            git.checkout(branch)
            unpushed = _count_commits('origin/{0}..{0}'.format(branch))
            unpulled = _count_commits('{0}..origin/{0}'.format(branch))
            if unpulled or unpushed:
                print ("  [{cwd}] {branch}: "
                       "{unpushed} ahead and {unpulled} behind origin").format(
                    cwd=path,
                    branch=branch,
                    unpushed=unpushed,
                    unpulled=unpulled,
                )
            else:
                print "  [{cwd}] {branch}: Everything up-to-date.".format(
                    cwd=path,
                    branch=branch,
                )
            if unpushed:
                unpushed_branches.append((path, branch))
            elif unpulled:
                print "  Fastforwarding your branch to origin"
                git.merge('--ff-only', 'origin/{0}'.format(branch))
    if unpushed_branches:
        print "The following branches have commits that need to be pushed:"
        for path, branch in unpushed_branches:
            print "  [{cwd}] {branch}".format(cwd=path, branch=branch)
        exit(1)
    else:
        print "All branches up-to-date."


def check_merges(config):
    merge_conflicts = []
    base_config = config
    for path, config in base_config.span_configs():
        git = get_git(path)

        git.checkout(config.trunk)
        for branch in config.branches:
            git.checkout(branch)
            print "  [{cwd}] {trunk} => {branch}".format(
                cwd=format_cwd(path),
                trunk=config.trunk,
                branch=branch,
            ),
            if not git_check_merge(config.trunk, branch, git=git):
                merge_conflicts.append((path, config.trunk, branch))
                print "FAIL"
            else:
                print "ok"
    if merge_conflicts:
        print "You must fix the following merge conflicts before rebuilding:"
        for cwd, trunk, branch in merge_conflicts:
            print "  [{cwd}] {trunk} => {branch}".format(
                cwd=format_cwd(cwd),
                branch=branch,
                trunk=trunk,
            )
        exit(1)
    else:
        print "No merge conflicts"


def rebuild_staging(config):
    for path, config in config.span_configs():
        git = get_git(path)
        git.checkout(config.trunk)
        git.checkout('-B', config.name, config.trunk)
        for branch in config.branches:
            print "  [{cwd}] Merging {branch} into {name}".format(
                cwd=path,
                branch=branch,
                name=config.name
            )
            git.merge(branch, '--no-edit')
        if config.submodules:
            for submodule in config.submodules:
                git.add(submodule)
            git.commit('-m', "update submodule refs", '--no-edit')
        # stupid safety check
        assert config.name != 'master'
        print "  [{cwd}] Force pushing to origin {name}".format(
            cwd=path,
            name=config.name,
        )
        git.push('origin', config.name, '--force')


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

if __name__ == '__main__':
    from sys import stdin
    import yaml
    config = yaml.load(stdin)
    config = BranchConfig.wrap(config)
    config.normalize()
    args = set(sys.argv[1:])
    verbose = '-v' in args
    args.discard('-v')
    if not args:
        args = set('fetch sync check rebuild'.split())
    with ShVerbose(verbose):
        if 'fetch' in args:
            fetch_remote(config)
        if 'sync' in args:
            sync_local_copies(config)
        if 'check' in args:
            check_merges(config)
        if 'rebuild' in args:
            rebuild_staging(config)
