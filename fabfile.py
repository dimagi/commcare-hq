from fabric.api import *
from fabric.contrib import console
from fabric import utils

env.root = '/opt/www.commcarehq.org_project'
env.code_repo = 'git://github.com/dimagi/commcare-hq.git'

def _join(*args):
    """
    We're deploying on Linux, so hard-code that path separator here.
    """
    return '/'.join(args)


def _setup_path():
    env.virtualenv_root = _join(env.root, 'env/cchq_www')
    env.code_root       = _join(env.root, 'src/commcare-hq')
    env.project_root    = _join(env.root, 'src/commcare-hq')

def production():
    """ use production environment on remote host"""
    env.code_branch = 'master'
    env.sudo_user = 'cchqwww'
    env.hosts = ['10.84.168.241']
    env.environment = 'production'
    env.user = prompt("Username: ", default=env.user)
    _setup_path()

    
def enter_virtualenv():
    """
    modify path to use virtualenv's python

    usage:

        with enter_virtualenv():
            run('python script.py')

    """
    return prefix('PATH=%(virtualenv_root)s/bin/:PATH' % env)


def deploy():
    """ deploy code to remote host by checking out the latest via git """
    require('root', provided_by=('staging', 'production'))
    if env.environment == 'production':
        if not console.confirm('Are you sure you want to deploy production?', default=False):
            utils.abort('Production deployment aborted.')

    with cd(env.code_root):
        sudo('git checkout %(code_branch)s' % env, user=env.sudo_user)
        sudo('git pull', user=env.sudo_user)
        sudo('git submodule init', user=env.sudo_user)
        sudo('git submodule update', user=env.sudo_user)
        with enter_virtualenv():
            sudo('pip install -r requirements.txt')
            sudo('python manage.py syncdb --noinput', user=env.sudo_user)
            sudo('python manage.py migrate --noinput', user=env.sudo_user)
            sudo('python manage.py collectstatic --noinput', user=env.sudo_user)
    service_restart()



def service_restart():
    """ restart cchq_www service on remote host.  This will call a stop, reload the initctl to
    have any config file updates be reloaded into intictl, then start cchqwww again.
    """
    require('root', provided_by=('staging', 'production'))
    with settings(sudo_user="root"):
        sudo('stop cchq_www', user=env.sudo_user)
        sudo('initctl reload-configuration', user=env.sudo_user)
        sudo('start cchq_www', user=env.sudo_user)
