"""
Server layout:
    ~/services/
        This contains two subfolders
            /apache/
            /supervisor/
        which hold the configurations for these applications
        for each environment (staging, demo, etc) running on the server.
        Theses folders are included in the global /etc/apache2 and
        /etc/supervisor configurations.

    ~/www/
        This folder contains the code, python environment, and logs
        for each environment (staging, demo, etc) running on the server.
        Each environment has its own subfolder named for its evironment
        (i.e. ~/www/staging/logs and ~/www/demo/logs).
"""
import uuid
from fabric.context_managers import settings, cd
from fabric.operations import require, local, prompt

import os, sys

from fabric.api import run, roles, execute, task, sudo, env, parallel
from fabric.contrib import files, console
from fabric import utils
import posixpath
from collections import defaultdict

if env.ssh_config_path and os.path.isfile(os.path.expanduser(env.ssh_config_path)):
    env.use_ssh_config = True

PROJECT_ROOT = os.path.dirname(__file__)
RSYNC_EXCLUDE = (
    '.DS_Store',
    '.git',
    '*.pyc',
    '*.example',
    '*.db',
    )
env.project = 'commcare-hq'
env.code_repo = 'git://github.com/dimagi/commcare-hq.git'

if not hasattr(env, 'code_branch'):
    print "WARNING: code_branch not specified, using 'master'. You can set it with '--set code_branch=<branch>'"
    env.code_branch = 'master'

env.home = "/home/cchq"
env.selenium_url = 'http://jenkins.dimagi.com/job/commcare-hq-post-deploy/buildWithParameters?token=%(token)s&TARGET=%(environment)s'
env.should_migrate = False # Default to safety
env.roledefs = {
        'django_celery': [],
        'django_app': [],
        'django_pillowtop': [], #for now combined with celery

        'django_monolith': [], # all of the above config - use this ONLY for single server config, lest deploy() will run multiple times in parallel causing bad contentions

        'formsplayer': [],
        'staticfiles': [],

        #package level configs that are not quite config'ed yet in this fabfile
        'couch': [],
        'pg': [],
        'rabbitmq': [],
        'lb': [],

        'deploy': [], #a placeholder to ensure deploy only runs once on a bogus, non functioning task, to split out the real tasks in the execute() block

    }

def format_env(current_env):
    """
    formats the current env to be a foo=bar,sna=fu type paring
    this is used for the make_supervisor_conf management command to pass current enviroment to make the supervisor conf files remotely
    instead of having to upload them from the fabfile.

    This is somewhat hacky in that we're going to cherry pick the env vars we want and make a custom dict to return
    """
    ret = dict()
    important_props = [
        'environment',
        'code_root',
        'log_dir',
        'sudo_user',
        'host_string',
        'project',
        'es_endpoint',
        'jython_home',
        'virtualenv_root',
        'django_port',
        'flower_port',
    ]

    for prop in important_props:
        ret[prop] = current_env.get(prop, '')
    return ','.join(['%s=%s' % (k, v) for k, v in ret.items()])



@task
def _setup_path():
    # using posixpath to ensure unix style slashes. See bug-ticket: http://code.fabfile.org/attachments/61/posixpath.patch
    env.root = posixpath.join(env.home, 'www', env.environment)
    env.log_dir = posixpath.join(env.home, 'www', env.environment, 'log')
    env.code_root = posixpath.join(env.root, 'code_root')
    env.code_root_preindex = posixpath.join(env.root, 'code_root_preindex')
    env.project_root = posixpath.join(env.code_root, env.project)
    env.project_media = posixpath.join(env.code_root, 'media')
    env.virtualenv_root = posixpath.join(env.root, 'python_env')
    env.virtualenv_root_preindex = posixpath.join(env.root, 'python_env_preindex')
    env.services = posixpath.join(env.home, 'services')
    env.jython_home = '/usr/local/lib/jython'
    env.db = '%s_%s' % (env.project, env.environment)

@task
def _set_apache_user():
    if what_os() == 'ubuntu':
        env.apache_user = 'www-data'
    elif what_os() == 'redhat':
        env.apache_user = 'apache'

@roles('lb')
def setup_apache_dirs():
    sudo('mkdir -p %(services)s/apache' % env, user=env.sudo_user)

@roles('django_celery', 'django_app', 'staticfiles')
def setup_dirs():
    """ create (if necessary) and make writable uploaded media, log, etc. directories """
    sudo('mkdir -p %(log_dir)s' % env, user=env.sudo_user)
    sudo('chmod a+w %(log_dir)s' % env, user=env.sudo_user)
    sudo('mkdir -p %(services)s/supervisor' % env, user=env.sudo_user)
    #execute(setup_apache_dirs)

@task
def staging():
    """ use staging environment on remote host"""
    env.code_branch = 'develop'
    env.sudo_user = 'commcare-hq'
    env.environment = 'staging'
    env.django_port = '9002'
    env.server_name = 'noneset'
    env.hosts = ['192.168.56.1']
    env.settings = '%(project)s.localsettings' % env
    env.host_os_map = None
    _setup_path()
    env.user = prompt("Username: ", default='dimagivm')
    env.es_endpoint = 'localhost'
    env.should_migrate = True

@task
def india():
    """Our production server in India."""
    env.home = '/home/commcarehq/'
    env.environment = 'india'
    env.sudo_user = 'commcarehq'
    env.hosts = ['220.226.209.82']
    env.user = prompt("Username: ", default=env.user)
    env.django_port = '8001'
    env.should_migrate = True

    _setup_path()
    env.virtualenv_root = posixpath.join(env.home, '.virtualenvs/commcarehq')
    env.virtualenv_root_preindex = posixpath.join(env.home, '.virtualenvs/commcarehq_preindex')

    env.roledefs = {
        'couch': [],
        'pg': [],
        'rabbitmq': [],
        'django_celery': [],
        'django_app': [],
        'django_pillowtop': [],
        'formsplayer': [],
        'staticfiles': [],
        'lb': [],
        'deploy': [],

        'django_monolith': ['220.226.209.82'],
    }
    env.roles = ['django_monolith']
    env.es_endpoint = 'localhost'
    env.flower_port = 5555



@task
def zambia():
    """Our production server in wv zambia."""
    env.sudo_user = 'cchq'
    env.environment = 'production'
    env.django_port = '9010'
    env.code_branch = 'master'
    env.should_migrate = True

    env.hosts = ['44.222.19.153']  # LIKELY THAT THIS WILL CHANGE

    _setup_path()

    env.roledefs = {
        'couch': [],
        'pg': [],
        'rabbitmq': [],
        'django_celery': [],
        'django_app': [],
        'django_pillowtop': [],
        'formsplayer': [],
        'staticfiles': [],
        'lb': [],
        'deploy': [],

        'django_monolith': ['44.222.19.153'],
    }
    env.roles = ['django_monolith']
    env.es_endpoint = 'localhost'
    env.flower_port = 5555


@task
def production():
    """ use production environment on remote host"""
    env.sudo_user = 'cchq'
    env.environment = 'production'
    env.django_port = '9010'
    env.code_branch = 'master'
    env.should_migrate = True

    #env.hosts = None
    env.roledefs = {
        'couch': ['hqdb0.internal.commcarehq.org'],
        'pg': ['hqdb0.internal.commcarehq.org'],
        'rabbitmq': ['hqdb0.internal.commcarehq.org'],
        'django_celery': ['hqdb0.internal.commcarehq.org'],
        'django_app': ['hqdjango0.internal.commcarehq.org', 'hqdjango1.internal.commcarehq.org', 'hqdjango2.internal.commcarehq.org'],
        'django_pillowtop': ['hqdb0.internal.commcarehq.org'],

        # for now, we'll have touchforms run on both hqdb and hqdjango0
        # will remove hqdjango0 once we verify it works well on hqdb0
        'formsplayer': ['hqdb0.internal.commcarehq.org'],
        'lb': [], #todo on apache level config
        'staticfiles': ['hqproxy0.internal.commcarehq.org'],
        'deploy': ['hqdb0.internal.commcarehq.org'], #this is a stub becuaue we don't want to be prompted for a host or run deploy too many times
        'django_monolith': [] # fab complains if this doesn't exist
    }


    env.server_name = 'commcare-hq-production'
    env.settings = '%(project)s.localsettings' % env
    env.host_os_map = None # e.g. 'ubuntu' or 'redhat'.  Gets autopopulated by what_os() if you don't know what it is or don't want to specify.
    env.roles = ['deploy', ]
    env.es_endpoint = 'hqes0.internal.commcarehq.org'''
    env.flower_port = 5555

    _setup_path()


@task
def realstaging():
    """ Use production data in a safe staging environment on remote host"""
    if not hasattr(env, 'code_branch') or env.code_branch == 'master':
        print "You must specify a code branch (not 'master') with --set code_branch=<branch>"
        sys.exit()

    env.sudo_user = 'cchq'
    env.environment = 'staging'
    env.django_port = '9010'

    env.should_migrate = True

    #env.hosts = None
    env.roledefs = {
        'couch': ['hqdb0-staging.internal.commcarehq.org'],
        'pg': ['hqdb0-staging.internal.commcarehq.org'],
        'rabbitmq': ['hqdb0-staging.internal.commcarehq.org'],
        'django_celery': ['hqdb0-staging.internal.commcarehq.org'],
        'django_app': ['hqdjango0-staging.internal.commcarehq.org','hqdjango1-staging.internal.commcarehq.org'],
        'django_pillowtop': ['hqdb0-staging.internal.commcarehq.org'],

        'formsplayer': ['hqdjango1-staging.internal.commcarehq.org'],
        'lb': [], #todo on apache level config
        'staticfiles': ['hqproxy0.internal.commcarehq.org'],
        'deploy': ['hqdb0-staging.internal.commcarehq.org'], #this is a stub because we don't want to be prompted for a host or run deploy too many times
        'django_monolith': [], # fab complains if this doesn't exist
    }

    env.es_endpoint = 'hqdjango1-staging.internal.commcarehq.org'''

    env.server_name = 'commcare-hq-staging'
    env.settings = '%(project)s.localsettings' % env
    env.host_os_map = None # e.g. 'ubuntu' or 'redhat'.  Gets autopopulated by what_os() if you don't know what it is or don't want to specify.
    env.roles = ['deploy', ]
    env.flower_port = 5555

    _setup_path()
    
@task
def preview():
    """ Use production data in a safe preview environment on remote host"""
    env.code_branch = 'master'
    env.sudo_user = 'cchq'
    env.environment = 'preview'
    env.django_port = '7999'
    #env.hosts = None
    env.should_migrate = False

    env.roledefs = {
        'couch': [],
        'pg': [],
        'rabbitmq': ['hqdb0-preview.internal.commcarehq.org'],
        'django_celery': ['hqdb0-preview.internal.commcarehq.org'],
        'django_app': ['hqdjango0-preview.internal.commcarehq.org','hqdjango1-preview.internal.commcarehq.org'],
        'django_pillowtop': ['hqdb0-preview.internal.commcarehq.org'],

        'formsplayer': ['hqdjango0-preview.internal.commcarehq.org'],
        'lb': [], #todo on apache level config
        'staticfiles': ['hqproxy0.internal.commcarehq.org'],
        'deploy': ['hqdb0-preview.internal.commcarehq.org'], #this is a stub because we don't want to be prompted for a host or run deploy too many times
        'django_monolith': [], # fab complains if this doesn't exist
    }

    env.es_endpoint = 'hqdjango1-preview.internal.commcarehq.org'''

    env.server_name = 'commcare-hq-preview'
    env.settings = '%(project)s.localsettings' % env
    env.host_os_map = None # e.g. 'ubuntu' or 'redhat'.  Gets autopopulated by what_os() if you don't know what it is or don't want to specify.
    env.roles = ['deploy', ]
    env.flower_port = 5556

    _setup_path()

@task
@roles('django_app','django_celery','staticfiles')
def install_packages():
    """Install packages, given a list of package names"""
    require('environment', provided_by=('staging', 'preview', 'production'))
    packages_list = ''
    installer_command = ''
    if what_os() == 'ubuntu':
        packages_list = 'apt-packages.txt'
        installer_command = 'apt-get install -y'
    elif what_os() == 'redhat':
        packages_list = 'yum-packages.txt'
        installer_command = 'yum install -y'
        return
    packages_file = posixpath.join(PROJECT_ROOT, 'requirements', packages_list)
    with open(packages_file) as f:
        packages = f.readlines()
    sudo("%s %s" % (installer_command, " ".join(map(lambda x: x.strip('\n\r'), packages))))


@task
@roles('django_app','django_celery','staticfiles')
@parallel
def upgrade_packages():
    """
    Bring all the installed packages up to date.
    This is a bad idea in RedHat as it can lead to an
    OS Upgrade (e.g RHEL 5.1 to RHEL 6).
    Should be avoided.  Run install packages instead.
    """
    require('environment', provided_by=('staging', 'preview', 'production'))
    if what_os() == 'ubuntu':
        sudo("apt-get update", shell=False)
        sudo("apt-get upgrade -y", shell=False)
    else:
        return #disabled for RedHat (see docstring)

@task
def what_os():
    with settings(warn_only=True):
        require('environment', provided_by=('staging','preview','production'))
        if getattr(env, 'host_os_map', None) is None:
            #prior use case of setting a env.remote_os did not work when doing multiple hosts with different os! Need to keep state per host!
            env.host_os_map = defaultdict(lambda: '')
        if env.host_os_map[env.host_string] == '':
            print 'Testing operating system type...'
            if(files.exists('/etc/lsb-release',verbose=True) and files.contains(text='DISTRIB_ID=Ubuntu', filename='/etc/lsb-release')):
                remote_os = 'ubuntu'
                print 'Found lsb-release and contains "DISTRIB_ID=Ubuntu", this is an Ubuntu System.'
            elif(files.exists('/etc/redhat-release',verbose=True)):
                remote_os = 'redhat'
                print 'Found /etc/redhat-release, this is a RedHat system.'
            else:
                print 'System OS not recognized! Aborting.'
                exit()
            env.host_os_map[env.host_string] = remote_os
        return env.host_os_map[env.host_string]

#@parallel
@roles('pg','django_celery','django_app','staticfiles', 'django_monolith')
@task
def setup_server():
    """Set up a server for the first time in preparation for deployments."""
    require('environment', provided_by=('staging', 'preview', 'production', 'india'))
    # Install required system packages for deployment, plus some extras
    # Install pip, and use it to install virtualenv
    install_packages()
    sudo("easy_install -U pip", user=env.sudo_user)
    sudo("pip install -U virtualenv", user=env.sudo_user)
    upgrade_packages()
    execute(create_pg_user)
    execute(create_pg_db)


@roles('pg', 'django_monolith')
@task
def create_pg_user():
    """Create the Postgres user."""
    require('environment', provided_by=('staging', 'preview', 'production'))
    sudo('createuser -D -R -P -s  %(sudo_user)s' % env, user='postgres')


@roles('pg', 'django_monolith')
@task
def create_pg_db():
    """Create the Postgres database."""
    require('environment', provided_by=('staging', 'preview', 'production'))
    sudo('createdb -O %(sudo_user)s %(db)s' % env, user='postgres')


@task
def bootstrap():
    """Initialize remote host environment (virtualenv, deploy, update) """
    require('root', provided_by=('staging', 'preview', 'production'))
    sudo('mkdir -p %(root)s' % env, shell=False, user=env.sudo_user)
    execute(clone_repo)

    update_code()
    execute(create_virtualenvs)
    execute(update_virtualenv)
    execute(setup_dirs)

    # copy localsettings if it doesn't already exist in case any management
    # commands we want to run now would error otherwise
    with cd(env.code_root):
        sudo('cp -n localsettings.example.py localsettings.py', user=env.sudo_user)
    with cd(env.code_root_preindex):
        sudo('cp -n localsettings.example.py localsettings.py', user=env.sudo_user)


@task
def unbootstrap():
    """Delete cloned repos and virtualenvs"""

    require('code_root', 'code_root_preindex', 'virtualenv_root',
            'virtualenv_root_preindex')

    with settings(warn_only=True):
        sudo(('rm -rf %(virtualenv_root)s %(virtualenv_root_preindex)s'
              '%(code_root)s %(code_root_preindex)s') % env, user=env.sudo_user)


#@parallel
@roles('django_celery', 'django_app', 'staticfiles', 'django_monolith')
def create_virtualenvs():
    """ setup virtualenv on remote host """
    require('virtualenv_root', 'virtualenv_root_preindex',
            provided_by=('staging', 'production', 'india'))

    args = '--distribute --no-site-packages'
    sudo('cd && virtualenv %s %s' % (args, env.virtualenv_root), user=env.sudo_user, shell=True)
    sudo('cd && virtualenv %s %s' % (args, env.virtualenv_root_preindex), user=env.sudo_user, shell=True)


#@parallel
@roles('django_celery', 'django_app', 'staticfiles', 'django_monolith')
def clone_repo():
    """ clone a new copy of the git repository """
    with settings(warn_only=True):
        with cd(env.root):
            exists_results = sudo('ls -d %(code_root)s' % env, user=env.sudo_user)
            if exists_results.strip() != env['code_root']:
                sudo('git clone %(code_repo)s %(code_root)s' % env, user=env.sudo_user)

            if not files.exists(env.code_root_preindex):
                sudo('git clone %(code_repo)s %(code_root_preindex)s' % env, user=env.sudo_user)


@task
def remove_submodule_source(path):
    """
    Remove submodule source folder.
    :param path: the name of the submodule source folder

    Example usage:
    > fab realstaging remove_submodule_source:ctable-src
    """
    if not console.confirm('Are you sure you want to delete submodules/{path} on {env.environment}?'.format(path=path, env=env), default=False):
        utils.abort('Action aborted.')

    require('root', provided_by=('staging', 'preview', 'production', 'india'))

    execute(_remove_submodule_source_main, path)
    execute(_remove_submodule_source_preindex, path)

@roles('django_app','django_celery', 'staticfiles', 'django_monolith')
@parallel
def _remove_submodule_source_main(path):
    with cd(env.code_root):
        sudo('rm -rf submodules/%s' % path, user=env.sudo_user)

@roles('pg', 'django_monolith')
@parallel
def _remove_submodule_source_preindex(path):
    with cd(env.code_root_preindex):
        sudo('rm -rf submodules/%s' % path, user=env.sudo_user)

@task
@roles('pg', 'django_monolith')
def preindex_views():
    if not env.should_migrate:
        utils.abort('Skipping preindex_views for "%s" because should_migrate = False' % env.environment)

    with cd(env.code_root_preindex):
        #update the codebase of the preindex dir...
        update_code(preindex=True)
        update_virtualenv(preindex=True) #no update to env - the actual deploy will do - this may break if a new dependency is introduced in preindex

        sudo('echo "%(virtualenv_root_preindex)s/bin/python %(code_root_preindex)s/manage.py \
             preindex_everything 8 %(user)s" --mail | at -t `date -d "5 seconds" \
             +%%m%%d%%H%%M.%%S`' % env, user=env.sudo_user)

@roles('django_app','django_celery', 'staticfiles', 'django_monolith')
@parallel
def update_code(preindex=False):
    if preindex:
        root_to_use = env.code_root_preindex
    else:
        root_to_use = env.code_root

    with cd(root_to_use):
        sudo('git fetch', user=env.sudo_user)
        sudo("git submodule foreach 'git fetch'", user=env.sudo_user)
        sudo('git checkout %(code_branch)s' % env, user=env.sudo_user)
        sudo('git reset --hard origin/%(code_branch)s' % env, user=env.sudo_user)
        sudo('git submodule sync', user=env.sudo_user)
        sudo('git submodule update --init --recursive', user=env.sudo_user)
        # remove all .pyc files in the project
        sudo("find . -name '*.pyc' -delete", user=env.sudo_user)

@roles('pg', 'django_monolith')
def mail_admins(subject, message):
    with cd(env.code_root):
        sudo('%(virtualenv_root)s/bin/python manage.py mail_admins --subject "%(subject)s" "%(message)s"' % \
                {'virtualenv_root': env.virtualenv_root,
                 'subject':subject,
                 'message':message },
             user=env.sudo_user)

@roles('pg', 'django_monolith')
def record_successful_deploy():
    with cd(env.code_root):
        sudo('%(virtualenv_root)s/bin/python manage.py record_deploy_success --user "%(user)s" --environment "%(environment)s" --mail_admins' % \
             {'virtualenv_root': env.virtualenv_root,
              'user': env.user,
              'environment': env.environment},
        user=env.sudo_user)

@task
def hotfix_deploy():
    """ deploy code to remote host by checking out the latest via git """
    if not console.confirm('Are you sure you want to deploy {env.environment}?'.format(env=env), default=False) or \
       not console.confirm('Did you run "fab {env.environment} preindex_views"? '.format(env=env), default=False) or \
       not console.confirm('HEY!!!! YOU ARE ONLY DEPLOYING CODE. THIS IS NOT A NORMAL DEPLOY. COOL???', default=False):
        utils.abort('Deployment aborted.')

    require('root', provided_by=('staging', 'preview', 'production', 'india'))
    run('echo ping!') #hack/workaround for delayed console response

    try:
        execute(update_code)
    except Exception:
        execute(mail_admins, "Deploy failed", "You had better check the logs.")
        raise
    else:
        execute(record_successful_deploy)
    finally:
        # hopefully bring the server back to life if anything goes wrong
        execute(services_restart)

@task
def deploy():
    """ deploy code to remote host by checking out the latest via git """
    if not console.confirm('Are you sure you want to deploy {env.environment}?'.format(env=env), default=False) or \
       not console.confirm('Did you run "fab {env.environment} preindex_views"? '.format(env=env), default=False):
        utils.abort('Deployment aborted.')

    require('root', provided_by=('staging', 'preview', 'production', 'india'))
    run('echo ping!') #hack/workaround for delayed console response

    try:
        execute(update_code)
        execute(update_virtualenv)
        execute(clear_services_dir)
        set_supervisor_config()
        if env.should_migrate:
            execute(migrate)
        execute(_do_collectstatic)
        execute(version_static)
        if env.should_migrate:
            execute(flip_es_aliases)
    except Exception:
        execute(mail_admins, "Deploy failed", "You had better check the logs.")
        raise
    else:
        execute(record_successful_deploy)
    finally:
        # hopefully bring the server back to life if anything goes wrong
        execute(services_restart)



@task
@roles('django_app','django_celery','staticfiles', 'django_monolith')#,'formsplayer')
@parallel
def update_virtualenv(preindex=False):
    """ update external dependencies on remote host assumes you've done a code update"""
    require('code_root', provided_by=('staging', 'preview', 'production', 'india'))
    if preindex:
        root_to_use = env.code_root_preindex
        env_to_use = env.virtualenv_root_preindex
    else:
        root_to_use = env.code_root
        env_to_use = env.virtualenv_root
    requirements = posixpath.join(root_to_use, 'requirements')
    with cd(root_to_use):
        cmd = ['export HOME=/home/%s && source %s/bin/activate && pip install' % (env.sudo_user, env_to_use)]
        cmd += ['--requirement %s' % posixpath.join(requirements, 'prod-requirements.txt')]
        cmd += ['--requirement %s' % posixpath.join(requirements, 'requirements.txt')]
        sudo(' '.join(cmd), user=env.sudo_user)


@roles('lb')
def touch_apache():
    """Touch apache conf files to trigger reload."""

    require('code_root', provided_by=('staging', 'preview', 'production'))
    apache_path = posixpath.join(posixpath.join(env.services, 'apache'), 'apache.conf')
    sudo('touch %s' % apache_path, user=env.sudo_user)



@roles('django_celery', 'django_app', 'django_monolith')
def touch_supervisor():
    """
    touch supervisor conf files to trigger reload. Also calls supervisorctl
    update to load latest supervisor.conf

    """
    require('code_root', provided_by=('staging', 'preview', 'production'))
    supervisor_path = posixpath.join(posixpath.join(env.services, 'supervisor'), 'supervisor.conf')
    sudo('touch %s' % supervisor_path, user=env.sudo_user)
    _supervisor_command('update')


@roles('django_app', 'django_celery', 'django_monolith')
@parallel
def clear_services_dir():
    """
    remove old confs from directory first
    the clear_supervisor_confs management command will scan the directory and find prefixed conf files of the supervisord files
    and delete them matching the prefix of the current server environment
    """
    services_dir = posixpath.join(env.services, u'supervisor')
    with cd(env.code_root):
        sudo(
            '%(virtualenv_root)s/bin/python manage.py clear_supervisor_confs --conf_location "%(conf_location)s"' %
            {
                'virtualenv_root': env.virtualenv_root,
                'conf_location': services_dir,
            }, user=env.sudo_user
        )


@roles('lb')
def configtest():
    """ test Apache configuration """
    require('root', provided_by=('staging', 'preview', 'production'))
    sudo('apache2ctl configtest')

@roles('lb')
def apache_reload():
    """ reload Apache on remote host """
    require('root', provided_by=('staging', 'preview', 'production'))
    if what_os() == 'redhat':
        sudo('/etc/init.d/httpd reload')
    elif what_os() == 'ubuntu':
        sudo('/etc/init.d/apache2 reload')


@roles('lb')
def apache_restart():
    """ restart Apache on remote host """
    require('root', provided_by=('staging', 'preview', 'production'))
    sudo('/etc/init.d/apache2 restart')

@task
def netstat_plnt():
    """ run netstat -plnt on a remote host """
    require('hosts', provided_by=('production', 'preview', 'staging'))
    sudo('netstat -plnt')


############################################################3
#Start service functions

@roles('django_app', 'django_celery','django_monolith')# 'formsplayer'
def services_start():
    ''' Start the gunicorn servers '''
    require('environment', provided_by=('staging', 'preview', 'demo', 'production'))
    _supervisor_command('update')
    _supervisor_command('reload')
    _supervisor_command('start  all')
######################################################

########################################################
#Stop service Functions

@roles('django_app', 'django_celery', 'django_monolith')#, 'formsplayer')
def services_stop():
    ''' Stop the gunicorn servers '''
    require('environment', provided_by=('staging', 'preview', 'demo', 'production'))
    _supervisor_command('stop all')
###########################################################

@task
def restart_services():
    if not console.confirm('Are you sure you want to restart the services on {env.environment}?'.format(env=env), default=False):
        utils.abort('Task aborted.')

    require('root', provided_by=('staging', 'preview', 'production', 'india'))
    execute(services_restart)

@roles('django_app', 'django_celery', 'django_monolith')#, 'formsplayer')
def services_restart():
    ''' Stop and restart all supervisord services'''
    require('environment', provided_by=('staging', 'preview', 'demo', 'production', 'india'))
    _supervisor_command('stop all')

    _supervisor_command('update')
    _supervisor_command('reload')
    _supervisor_command('start  all')
#
@roles('django_celery','django_monolith')
def migrate():
    """ run south migration on remote environment """
    require('code_root', provided_by=('production', 'demo', 'preview', 'staging', "india"))
    with cd(env.code_root):
        sudo('%(virtualenv_root)s/bin/python manage.py sync_finish_couchdb_hq' % env, user=env.sudo_user)
        sudo('%(virtualenv_root)s/bin/python manage.py syncdb --noinput' % env, user=env.sudo_user)
        sudo('%(virtualenv_root)s/bin/python manage.py migrate --noinput' % env, user=env.sudo_user)


@roles('django_celery','django_monolith')
def flip_es_aliases():
    """Flip elasticsearch aliases to the lastest version """
    require('code_root', provided_by=('production', 'demo', 'preview', 'staging', "india"))
    with cd(env.code_root):
        sudo('%(virtualenv_root)s/bin/python manage.py ptop_es_manage --flip_all_aliases' % env, user=env.sudo_user)

@roles('staticfiles', 'django_monolith')
def _do_collectstatic():
    """
    Collect static after a code update
    """
    with cd(env.code_root):
        sudo('%(virtualenv_root)s/bin/python manage.py collectstatic --noinput' % env, user=env.sudo_user)

@roles('django_app', 'django_monolith')
@parallel
def version_static():
    """
    Put refs on all static references to prevent stale browser cache hits when things change.
    This needs to be run on the WEB WORKER since the web worker governs the actual static
    reference.
    """
    with cd(env.code_root):
        sudo('rm -f tmp.sh resource_versions.py; %(virtualenv_root)s/bin/python manage.py   \
             printstatic > tmp.sh; bash tmp.sh > resource_versions.py' % env, user=env.sudo_user)



@task
@roles('staticfiles',)
def collectstatic():
    """ run collectstatic on remote environment """
    require('code_root', provided_by=('production', 'demo', 'preview', 'staging'))
    update_code()
    _do_collectstatic()


@task
def reset_local_db():
    """ Reset local database from remote host """
    require('code_root', provided_by=('production', 'preview', 'staging'))
    if env.environment == 'production':
        utils.abort('Local DB reset is for staging environment only')
    question = 'Are you sure you want to reset your local '\
               'database with the %(environment)s database?' % env
    sys.path.append('.')
    if not console.confirm(question, default=False):
        utils.abort('Local database reset aborted.')
    local_db = loc['default']['NAME']
    remote_db = remote['default']['NAME']
    with settings(warn_only=True):
        local('dropdb %s' % local_db)
    local('createdb %s' % local_db)
    host = '%s@%s' % (env.user, env.hosts[0])
    local('ssh -C %s sudo -u commcare-hq pg_dump -Ox %s | psql %s' % (host, remote_db, local_db))
@task
def fix_locale_perms():
    """ Fix the permissions on the locale directory """
    require('root', provided_by=('staging', 'preview', 'production'))
    _set_apache_user()
    locale_dir = '%s/locale/' % env.code_root
    sudo('chown -R %s %s' % (env.sudo_user, locale_dir), user=env.sudo_user)
    sudo('chgrp -R %s %s' % (env.apache_user, locale_dir), user=env.sudo_user)
    sudo('chmod -R g+w %s' % (locale_dir), user=env.sudo_user)

@task
def commit_locale_changes():
    """ Commit locale changes on the remote server and pull them in locally """
    fix_locale_perms()
    with cd(env.code_root):
        sudo('-H -u %s git add commcare-hq/locale' % env.sudo_user, user=env.sudo_user)
        sudo('-H -u %s git commit -m "updating translation"' % env.sudo_user, user=env.sudo_user)
    local('git pull ssh://%s%s' % (env.host, env.code_root))

def _rebuild_supervisor_conf_file(filename):
    with cd(env.code_root):
        sudo(
            '%(virtualenv_root)s/bin/python manage.py make_supervisor_conf --conf_file "%(filename)s" --conf_destination "%(destination)s" --params "%(params)s"' % {
                'virtualenv_root': env.virtualenv_root,
                'filename': filename,
                'destination': posixpath.join(env.services, 'supervisor'),
                'params': format_env(env)
            },
            user=env.sudo_user)

@roles('django_celery', 'django_monolith')
def set_celery_supervisorconf():
    _rebuild_supervisor_conf_file('supervisor_celery_main.conf')

    #hacky hack to not
    #have staging environments send out reminders
    if env.environment not in ['staging', 'preview', 'realstaging']:
        _rebuild_supervisor_conf_file('supervisor_celery_beat.conf')
        _rebuild_supervisor_conf_file('supervisor_celery_periodic.conf')
    _rebuild_supervisor_conf_file('supervisor_celery_flower.conf')
    _rebuild_supervisor_conf_file('supervisor_couchdb_lucene.conf') #to be deprecated

    #in reality this also should be another machine if the number of listeners gets too high
    if env.environment not in ['preview']:
        #preview environment should not run pillowtop and index stuff, just rely on what's on staging
        _rebuild_supervisor_conf_file('supervisor_pillowtop.conf')




@roles('django_app', 'django_monolith')
def set_djangoapp_supervisorconf():
    _rebuild_supervisor_conf_file('supervisor_django.conf')


@roles('remote_es')
def set_elasticsearch_supervisorconf():
    _rebuild_supervisor_conf_file('supervisor_elasticsearch.conf')

@roles('formsplayer', 'django_monolith')
def set_formsplayer_supervisorconf():
    _rebuild_supervisor_conf_file('supervisor_formsplayer.conf')

def set_supervisor_config():
    """Upload and link Supervisor configuration from the template."""
    require('environment', provided_by=('staging', 'preview', 'demo', 'production', 'india'))
    execute(set_celery_supervisorconf)
    execute(set_djangoapp_supervisorconf)
    execute(set_formsplayer_supervisorconf)

    #if needing tunneled ES setup, comment this back in
    #execute(set_elasticsearch_supervisorconf)



def _supervisor_command(command):
    require('hosts', provided_by=('staging', 'preview', 'production'))
    #if what_os() == 'redhat':
        #cmd_exec = "/usr/bin/supervisorctl"
    #elif what_os() == 'ubuntu':
        #cmd_exec = "/usr/local/bin/supervisorctl"
    sudo('supervisorctl %s' % (command), shell=False)

@task
def update_apache_conf():
    require('code_root', 'django_port')

    with cd(env.code_root):
        tmp = "/tmp/cchq"
        sudo('%s/bin/python manage.py mkapacheconf %s > %s'
              % (env.virtualenv_root, env.django_port, tmp), user=env.sudo_user)
        sudo('cp -f %s /etc/apache2/sites-available/cchq' % tmp, user='root')

    with settings(warn_only=True):
        sudo('a2dissite 000-default', user='root')
        sudo('a2dissite default', user='root')

    sudo('a2enmod proxy_http', user='root')
    sudo('a2ensite cchq', user='root')
    sudo('service apache2 reload', user='root')


# tests

@task
def selenium_test():
    require('environment', provided_by=('staging', 'preview', 'demo', 'production', 'india'))
    prompt("Jenkins username:", key="jenkins_user", default="selenium")
    prompt("Jenkins password:", key="jenkins_password")
    url = env.selenium_url % {"token": "foobar", "environment": env.environment}
    local("curl --user %(user)s:%(pass)s '%(url)s'" % \
          {'user': env.jenkins_user, 'pass': env.jenkins_password, 'url': url})
    
