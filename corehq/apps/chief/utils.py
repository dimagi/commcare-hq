import itertools

from fab import chief, fabfile
from fabric.api import execute


def update_chief_code(env):
    """
    Remotely updates the Chief's code base
    """
    fabfile.clear_code_branch()
    fabfile.load_env(env)
    getattr(fabfile, env)()
    execute(chief.update_chief_code)


def get_uncommitted_submodules(env):
    """
    Gets a list of Chief's uncommitted submodules
    """
    fabfile.clear_code_branch()
    fabfile.load_env(env)
    getattr(fabfile, env)()
    submodules = execute(chief.chief_uncommitted_submodules)
    return list(itertools.chain(*submodules.values()))


def commit_submodules(env, submodules):
    """
    Given a list of uncommitted submodules, commit those submodules to master
    """


def build_staging(env):
    fabfile.clear_code_branch()
    fabfile.load_env(env)
    getattr(fabfile, env)()
    execute(chief.build_staging)


def trigger_chief_deploy(env):
    """
    Triggers Chief to kick off a deploy
    """
    fabfile.clear_code_branch()
    fabfile.load_env(env)
    getattr(fabfile, env)()
    execute(chief.chief_deploy, env)


def get_machines(env):
    """
    Gets list of machines
    """
    fabfile.clear_code_branch()
    fabfile.load_env(env)
    getattr(fabfile, env)()
    return list(set([host for role in fabfile.env['roledefs'].values() for host in role]))


def get_releases(envs):
    releases = {}
    for env in envs:
        fabfile.clear_code_branch()
        fabfile.load_env(env)
        getattr(fabfile, env)()
        release_hash = execute(fabfile.get_releases, 3)
        releases[env] = sorted(list(set(itertools.chain(*release_hash.values()))), reverse=True)
    return releases
