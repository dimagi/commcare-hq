import sys

from fabric.api import task, env, roles, sudo, settings
from fabric.context_managers import cd

from .fabfile import load_env, ROLES_CHIEF, _require_target, _pull_latest


@task
@roles(ROLES_CHIEF)
def chief_deploy(env):

    # Dynamically call environment setup
    getattr(sys.modules[__name__], env)()
    env.is_chief_deploy = True

    _require_target()
    with cd(env.chief_dir):
        if env == 'staging':
            sudo('git checkout autostaging')
        sudo('fab {} awesome_deploy'.format(env))


@task
@roles(ROLES_CHIEF)
def update_chief_code():
    with cd(env.chief_dir):
        _pull_latest()


@task
@roles(ROLES_CHIEF)
def build_staging():
    with cd(env.chief_dir):
        sudo('source python_env/bin/activate && scripts/rebuildstaging --no-push')


@task
@roles(ROLES_CHIEF)
def chief_uncommitted_submodules():
    with cd(env.chief_dir):
        submodules_cmd = "git submodule | awk '{ print $2 }'"
        uncommitted_files_cmd = "git submodule status | grep \"^\+\" | awk '{ print $2 }'"
        uncommitted_submodules = sudo('join <({}) <({})'.format(submodules_cmd, uncommitted_files_cmd))

    return uncommitted_submodules.split()
