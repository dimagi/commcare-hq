from fabric.api import *
from fabric.contrib import console
from fabric import utils

env.code_repo = 'git://github.com/dimagi/commcare-hq.git'

def _join(*args):
    """
    We're deploying on Linux, so hard-code that path separator here.
    """
    return '/'.join(args)

def production():
    """ use production environment on remote host"""
    env.root = root = '/opt/www.commcarehq.org_project'
    env.virtualenv_root = _join(root, 'env/cchq_www')
    env.code_root       = _join(root, 'src/commcare-hq')
    env.code_branch = 'master'
    env.sudo_user = 'cchqwww'
    env.hosts = ['10.84.168.241']
    env.environment = 'production'
    env.user = prompt("Username: ", default=env.user)
    env.restart_server = True

def migration():
    """pull from staging branch into production to do a data migration"""
    production()
    env.code_branch = 'staging'
    env.restart_server = False

def staging():
    """ use staging environment on remote host"""
    env.root = root = '/home/dimagivm/'
    env.virtualenv_root = _join(root, 'cchq')
    env.code_root       = _join(root, 'commcare-hq')
    env.code_branch = 'staging'
    env.sudo_user = 'root'
    env.hosts = ['192.168.7.223']
    env.environment = 'staging'
    env.user = prompt("Username: ", default='dimagivm')

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
        sudo('git pull', user=env.sudo_user)
        sudo('git checkout %(code_branch)s' % env, user=env.sudo_user)
        sudo('git pull', user=env.sudo_user)
        sudo('git submodule update --init --recursive', user=env.sudo_user)
        with enter_virtualenv():
            sudo('pip install -r requirements.txt')
            sudo('python manage.py syncdb --noinput', user=env.sudo_user)
            sudo('python manage.py migrate --noinput', user=env.sudo_user)
            sudo('python manage.py collectstatic --noinput', user=env.sudo_user)
            try: sudo('rm tmp.sh', user=env.sudo_user)
            except Exception:
                pass
            try: sudo('rm resource_versions.py', user=env.sudo_user)
            except Exception:
                pass
            sudo('python manage.py printstatic > tmp.sh; bash tmp.sh > resource_versions.py', user=env.sudo_user)
        # remove all .pyc files in the project
        sudo("find . -name '*.pyc' -delete")
        
    if env.environment == "production" and env.restart_server:
        service_restart()



def service_restart():
    """
    restart cchq_www service on remote host.  This will call a stop, reload the initctl to
    have any config file updates be reloaded into intictl, then start cchqwww again.

    """
    require('root', provided_by=('staging', 'production'))
    with settings(sudo_user="root"):
        sudo('stop cchq_www', user=env.sudo_user)
        sudo('initctl reload-configuration', user=env.sudo_user)
        sudo('start cchq_www', user=env.sudo_user)

def service_stop():
    """
    stop cchq_www service on remote host.

    """
    require('root', provided_by=('staging', 'production'))
    with settings(sudo_user="root"):
        sudo('stop cchq_www', user=env.sudo_user)
