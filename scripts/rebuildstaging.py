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


def sync_local_copies(config):
    base_config = config
    unpushed_branches = []

    def _count_commits(compare_spec):
        return int(sh.wc(git.log(compare_spec, '--oneline', _piped=True), '-l'))

    for path, config in base_config.span_configs():
        git = get_git(path)
        with OriginalBranch(git):
            for branch in [config.trunk] + config.branches:
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
        with OriginalBranch(git):
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
            git = get_git(cwd)
            print_merge_details(branch, trunk, git)
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
