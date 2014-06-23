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

from gevent import monkey
monkey.patch_all(time=False, select=False)

import os
import jsonobject
import sh
import sys
import contextlib
import gevent

from sh_verbose import ShVerbose
from gitutils import (
    OriginalBranch,
    get_git,
    git_check_merge,
    print_merge_details,
)


class BranchConfig(jsonobject.JsonObject):
    trunk = jsonobject.StringProperty()
    name = jsonobject.StringProperty()
    branches = jsonobject.ListProperty(unicode)
    submodules = jsonobject.DictProperty(lambda: BranchConfig)

    def normalize(self):
        for submodule, subconfig in self.submodules.items():
            subconfig.trunk = subconfig.trunk or self.trunk
            subconfig.name = subconfig.name or self.name
            subconfig.normalize()

    def span_configs(self, path=('.',)):
        for submodule, subconfig in self.submodules.items():
            for item in subconfig.span_configs(path + (submodule,)):
                yield item
        yield os.path.join(*path), self


def fetch_remote(base_config):
    jobs = []
    for path in set(path for path, _ in base_config.span_configs()):
        git = get_git(path)
        print "  [{cwd}] fetching all".format(cwd=path)
        jobs.append(gevent.spawn(git.fetch, '--all'))
    gevent.joinall(jobs)
    print "All branches fetched"


def has_local(git, branch):
    """Return true if the named branch exists"""
    ref = "refs/heads/{}".format(branch)
    try:
        out = git("show-ref", "--verify", "--quiet", ref)
    except sh.ErrorReturnCode:
        return False
    return out.exit_code == 0


def origin(branch):
    return "origin/{}".format(branch)


def sync_local_copies(config):
    base_config = config
    unpushed_branches = []

    def _count_commits(compare_spec):
        return int(sh.wc(git.log(compare_spec, '--oneline', _piped=True), '-l'))

    for path, config in base_config.span_configs():
        git = get_git(path)
        with OriginalBranch(git):
            for branch in [config.trunk] + config.branches:
                if not has_local(git, branch):
                    continue
                git.checkout(branch)
                unpushed = _count_commits('origin/{0}..{0}'.format(branch))
                unpulled = _count_commits('{0}..origin/{0}'.format(branch))
                if unpulled or unpushed:
                    print ("  [{cwd}] {branch}: {unpushed} ahead "
                           "and {unpulled} behind origin").format(
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
                    git.merge('--ff-only', origin(branch))
    if unpushed_branches:
        print "The following branches have commits that need to be pushed:"
        for path, branch in unpushed_branches:
            print "  [{cwd}] {branch}".format(cwd=path, branch=branch)
        exit(1)
    else:
        print "All branches up-to-date."


def check_merges(config, print_details=True):
    merge_conflicts = []
    not_found = []
    base_config = config
    for path, config in base_config.span_configs():
        git = get_git(path)
        with OriginalBranch(git):
            trunk = origin(config.trunk)
            git.checkout('-B', config.name, trunk, '--no-track')
            for branch in config.branches:
                if not has_local(git, branch):
                    branch = origin(branch)
                print "  [{cwd}] {trunk} => {branch}".format(
                    cwd=format_cwd(path),
                    trunk=trunk,
                    branch=branch,
                ),
                try:
                    git.checkout(branch)
                except sh.ErrorReturnCode_1 as e:
                    assert (
                        "error: pathspec '%s' did not "
                        "match any file(s) known to git." % branch) in e.stderr, e.stderr
                    not_found.append((path, branch))
                    print "NOT FOUND"
                    continue
                if not git_check_merge(config.name, branch, git=git):
                    merge_conflicts.append((path, origin(config.trunk), branch))
                    print "FAIL"
                else:
                    print "ok"
    if not_found:
        print "You must remove the following branches before rebuilding:"
        for cwd, branch in not_found:
            print "  [{cwd}] {branch}".format(
                cwd=format_cwd(cwd),
                branch=branch,
            )
    if merge_conflicts:
        print "You must fix the following merge conflicts before rebuilding:"
        for cwd, trunk, branch in merge_conflicts:
            print "  [{cwd}] {trunk} => {branch}".format(
                cwd=format_cwd(cwd),
                branch=branch,
                trunk=trunk,
            )
            git = get_git(cwd)
            if print_details:
                print_merge_details(branch, trunk, git)

    if merge_conflicts or not_found:
        exit(1)
    else:
        print "No merge conflicts"


def rebuild_staging(config):
    all_configs = list(config.span_configs())
    context_manager = contextlib.nested(*[OriginalBranch(get_git(path))
                                          for path, _ in all_configs])
    with context_manager:
        for path, config in all_configs:
            git = get_git(path)
            git.checkout('-B', config.name, origin(config.trunk), '--no-track')
            for branch in config.branches:
                if not has_local(git, branch):
                    branch = origin(branch)
                print "  [{cwd}] Merging {branch} into {name}".format(
                    cwd=path,
                    branch=branch,
                    name=config.name
                )
                git.merge(branch, '--no-edit')
            if config.submodules:
                for submodule in config.submodules:
                    git.add(submodule)
                git.commit('-m', "update submodule refs", '--no-edit',
                           '--allow-empty')
            # stupid safety check
            assert config.name != 'master'
            print "  [{cwd}] Force pushing to origin {name}".format(
                cwd=path,
                name=config.name,
            )
            force_push(git, config.name)


def force_push(git, branch):
    try:
        git.push('origin', branch, '--force')
    except sh.ErrorReturnCode_128 as e:
        # oops we're using a read-only URL, so change to the suggested url
        try:
            line = sh.grep(git.remote("-v"),
                           '-E', '^origin.(https|git)://github\.com/.*\(push\)$')
        except sh.ErrorReturnCode_1:
            raise e
        old_url = line.strip().split()[1]
        prefix = "git" if old_url.startswith("git:") else "https"
        new_url = old_url.replace(prefix + "://github.com/", "git@github.com:")
        print("    {} -> {}".format(old_url, new_url))
        git.remote('set-url', 'origin', new_url)
        git.push('origin', branch, '--force')


def format_cwd(cwd):
    return os.path.join(cwd) if cwd else '.'


class DisableGitHooks(object):
    already_disabled = None

    def __init__(self, path='.git/hooks'):
        import uuid
        self.path = path
        self.guid = uuid.uuid4().hex

    @property
    def hidden_path(self):
        return self.path + '-' + self.guid

    def __enter__(self):
        try:
            sh.test('-d', self.path)
            self.already_disabled = False
        except sh.ErrorReturnCode_1:
            self.already_disabled = True
        else:
            sh.mv(self.path, self.hidden_path)

    def __exit__(self, exc_type, exc_val, exc_tb):
        if not self.already_disabled:
            sh.mv(self.hidden_path, self.path)


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
    with DisableGitHooks(), ShVerbose(verbose):
        if 'fetch' in args:
            fetch_remote(config)
        if 'sync' in args:
            sync_local_copies(config)
        if 'check' in args:
            check_merges(config)
        if 'rebuild' in args:
            rebuild_staging(config)
