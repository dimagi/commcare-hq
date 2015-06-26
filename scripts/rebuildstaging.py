"""
This file is meant to be used in the following manner:

$ python make_rebuild_staging.py < staging.yaml [-v] [--no-push] [fetch] [sync] [rebuild]

Where staging.yaml looks as follows:

    trunk: master
    name: autostaging
    branches:
      - feature1
      - feature2
      - forkowner:feature3 # branch from fork of repository
    submodules:
      submodules/module1:
        branches:
          - feature1
          - forkowner:feature2 # branch from fork of repository
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


def fetch_remote(base_config, name="origin"):
    jobs = []
    seen = set()
    fetched = set()
    for path, config in base_config.span_configs():
        if path in seen:
            continue
        seen.add(path)
        git = get_git(path)
        print "  [{cwd}] fetching {name}".format(cwd=path, name=name)
        jobs.append(gevent.spawn(git.fetch, name))
        for branch in (b for b in config.branches if ":" in b):
            remote, branch = branch.split(":", 1)
            if remote not in git.remote().split():
                url = remote_url(git, remote)
                print("  [{path}] adding remote: {remote} -> {url}"
                      .format(**locals()))
                git.remote("add", remote, url)
            print "  [{path}] fetching {remote} {branch}".format(**locals())
            jobs.append(gevent.spawn(git.fetch, remote, branch))
            fetched.add(remote)
    gevent.joinall(jobs)
    print "fetched {}".format(", ".join(['origin'] + sorted(fetched)))


def remote_url(git, remote, original="origin"):
    origin_url = sh.grep(git.remote("-v"), original).split()[1]
    repo_name = origin_url.rsplit("/", 1)[1]
    return "https://github.com/{}/{}".format(remote, repo_name)


def has_ref(git, ref):
    """Return true if the named branch exists"""
    try:
        out = git("show-ref", "--verify", "--quiet", ref)
    except sh.ErrorReturnCode:
        return False
    return out.exit_code == 0


def has_local(git, branch):
    """Return true if the named local branch exists"""
    return has_ref(git, "refs/heads/{}".format(branch))


def has_remote(git, ref):
    """Return true if the named remote branch exists

    :param ref: Remote ref (example: origin/branch-name)
    """
    return has_ref(git, "refs/remotes/{}".format(ref))


def origin(branch):
    return "origin/{}".format(branch)


def sync_local_copies(config, push=True):
    base_config = config
    unpushed_branches = []

    def _count_commits(compare_spec):
        return int(sh.wc(git.log(compare_spec, '--oneline', _piped=True), '-l'))

    for path, config in base_config.span_configs():
        git = get_git(path)
        with OriginalBranch(git):
            for branch in [config.trunk] + config.branches:
                if ":" in branch or not has_local(git, branch):
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
    if unpushed_branches and push:
        print "The following branches have commits that need to be pushed:"
        for path, branch in unpushed_branches:
            print "  [{cwd}] {branch}".format(cwd=path, branch=branch)
        exit(1)
    else:
        print "All branches up-to-date."


def rebuild_staging(config, print_details=True, push=True):
    merge_conflicts = []
    not_found = []
    all_configs = list(config.span_configs())
    context_manager = contextlib.nested(*[OriginalBranch(get_git(path))
                                          for path, _ in all_configs])
    with context_manager:
        for path, config in all_configs:
            git = get_git(path)
            git.checkout('-B', config.name, origin(config.trunk), '--no-track')
            for branch in config.branches:
                remote = ":" in branch
                if remote or not has_local(git, branch):
                    if remote:
                        remote_branch = branch.replace(":", "/", 1)
                    else:
                        remote_branch = origin(branch)
                    if not has_remote(git, remote_branch):
                        not_found.append((path, branch))
                        print "  [{cwd}] {branch} NOT FOUND".format(
                            cwd=format_cwd(path),
                            branch=branch,
                        )
                        continue
                    branch = remote_branch
                print "  [{cwd}] Merging {branch} into {name}".format(
                    cwd=path,
                    branch=branch,
                    name=config.name
                ),
                try:
                    git.merge(branch, '--no-edit')
                except sh.ErrorReturnCode_1:
                    merge_conflicts.append((path, branch, config))
                    try:
                        git.merge("--abort")
                    except sh.ErrorReturnCode_128:
                        pass
                    print "FAIL"
                else:
                    print "ok"
            if config.submodules:
                for submodule in config.submodules:
                    git.add(submodule)
                git.commit('-m', "update submodule refs", '--no-edit',
                           '--allow-empty')
        if push and not (merge_conflicts or not_found):
            for path, config in all_configs:
                # stupid safety check
                assert config.name != 'master', path
                print "  [{cwd}] Force pushing to origin {name}".format(
                    cwd=path,
                    name=config.name,
                )
                force_push(get_git(path), config.name)

    if not_found:
        print "You must remove the following branches before rebuilding:"
        for cwd, branch in not_found:
            print "  [{cwd}] {branch}".format(
                cwd=format_cwd(cwd),
                branch=branch,
            )
    if merge_conflicts:
        print "You must fix the following merge conflicts before rebuilding:"
        for cwd, branch, config in merge_conflicts:
            print "\n[{cwd}] {branch} => {name}".format(
                cwd=format_cwd(cwd),
                branch=branch,
                name=config.name,
            )
            git = get_git(cwd)
            if print_details:
                print_merge_details(branch, config.name, git,
                                    known_branches=config.branches)

    if merge_conflicts or not_found:
        exit(1)


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


def main():
    from sys import stdin
    import yaml
    config = yaml.load(stdin)
    config = BranchConfig.wrap(config)
    config.normalize()
    args = set(sys.argv[1:])
    verbose = '-v' in args
    do_push = '--no-push' not in args
    args.discard('-v')
    args.discard('--no-push')
    if not args:
        args = set('fetch sync rebuild'.split())
    with DisableGitHooks(), ShVerbose(verbose):
        if 'fetch' in args:
            fetch_remote(config)
        if 'sync' in args:
            sync_local_copies(config, push=do_push)
        if 'rebuild' in args:
            rebuild_staging(config, push=do_push)


if __name__ == '__main__':
    main()
