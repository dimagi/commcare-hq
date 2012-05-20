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
    env.pre_code_root   = _join(root, 'src/_commcare-hq')
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

def india():
    """Our production server in India."""
    env.root = root = '/home/commcarehq'
    env.virtualenv_root = _join(root, '.virtualenvs/commcarehq')
    env.code_root       = _join(root, 'src/commcare-hq')
    env.pre_code_root   = _join(root, 'src/_commcare-hq')
    env.code_branch = 'master'
    env.sudo_user = 'commcarehq'
    env.hosts = ['220.226.209.82']
    env.environment = 'india'
    env.user = prompt("Username: ", default=env.user)

def rackspace():
    """Our production server on Rackspace.  This is to be come the new production() method"""
    env.root = root = '/home/commcarehq'
    env.virtualenv_root = _join(root, '.virtualenvs/commcarehq')
    env.code_root       = _join(root, 'src/commcare-hq')
    env.pre_code_root   = _join(root, 'src/_commcare-hq')
    env.code_branch = 'master'
    env.sudo_user = 'commcarehq'
    env.hosts = ['192.168.100.62']
    env.environment = 'rackspace'
    env.user = prompt("Username: ", default=env.user)

def enter_virtualenv():
    """
    modify path to use virtualenv's python

    usage:

        with enter_virtualenv():
            run('python script.py')

    """
    return prefix('PATH=%(virtualenv_root)s/bin/:$PATH' % env)

def preindex_views():
    with cd(env.pre_code_root):
        _update_code()
        with enter_virtualenv():
            sudo('nohup python manage.py sync_prepare_couchdb > preindex_views.out 2> preindex_views.err', user=env.sudo_user)

def _update_code():
    sudo('git pull', user=env.sudo_user)
    sudo('git checkout %(code_branch)s' % env, user=env.sudo_user)
    sudo('git pull', user=env.sudo_user)
    sudo('git submodule sync', user=env.sudo_user)
    sudo('git submodule update --init --recursive', user=env.sudo_user)

def deploy():
    """ deploy code to remote host by checking out the latest via git """
    require('root', provided_by=('staging', 'production', 'india', 'rackspace'))
    if env.environment in ('production', 'india', 'rackspace'):
        if not console.confirm('Are you sure you want to deploy to %s?' % env.environment, default=False):
            utils.abort('Deployment aborted.')

    with cd(env.code_root):
        _update_code()
        with enter_virtualenv():
            sudo('pip install -r requirements.txt', user=env.sudo_user)
            sudo('python manage.py make_bootstrap direct-lessc', user=env.sudo_user)
            sudo('python manage.py sync_finish_couchdb', user=env.sudo_user)
            sudo('python manage.py syncdb --noinput', user=env.sudo_user)
            sudo('python manage.py migrate --noinput', user=env.sudo_user)
            sudo('python manage.py collectstatic --noinput', user=env.sudo_user)
            sudo('rm -f tmp.sh resource_versions.py; python manage.py printstatic > tmp.sh; bash tmp.sh > resource_versions.py', user=env.sudo_user)
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
