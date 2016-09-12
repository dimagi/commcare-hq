from optparse import OptionParser
import os.path
import os
from subprocess import Popen, PIPE
import glob
import shutil
from jinja2 import Template
import re
import itertools

ROOT = os.path.dirname(os.path.abspath(__file__))
def _path(*relpath):
    """normalize paths relative to the main directory for offline cloudcare"""
    return os.path.normpath(os.path.join(ROOT, *relpath))

def run(cmd, echo=True):
    """execute a command"""
    if echo:
        print '>>', cmd
    p = Popen(cmd, shell=True)
    p.communicate()
    if p.returncode:
        raise RuntimeError('command failed')

TF_SRC_DIR = _path('..', 'backend')   # touchforms code
TF_JARS_DIR = _path('..', 'backend', 'jrlib')   # touchforms external dependencies
TF_INST_DIR = _path('src', 'main', 'resources', 'Lib', 'touchforms')   # where the touchforms
   # code will go in the web start jar build tree
DIST_DIR = _path('dist')   # output dir of this build script
JYTHON_JAR = _path('jython-standalone-2.5.2.jar')

def mkdir(path):
    """create directory if needed (all ancestor dirs must exist)"""
    if not os.path.exists(path):
        print '** mkdir', path
        os.mkdir(path)

def wipedir(path):
    """remove all contents of a dir (but not the dir itself)"""
    if os.path.exists(path):
        shutil.rmtree(path)
    mkdir(path)

def copy_pattern(pattern, dst):
    """cp /a/b/*.c /d/e/"""
    for path in glob.glob(pattern):
        shutil.copy(path, dst)


def register_deps():
    """register jar dependencies with maven so that it can find them during build"""
    jars = itertools.chain([JYTHON_JAR], glob.glob(os.path.join(TF_JARS_DIR, '*.jar')))
    for jar in jars:
        filename = os.path.split(jar)[1]
        m = re.match('(?P<base>.*?)([.-]?[0-9.]+)?.jar', filename)
        basename = m.group('base')
        run('mvn install:install-file -Dfile=%s -DgroupId=touchforms-deps -DartifactId=%s -Dversion=latest -Dpackaging=jar' % (jar, basename))

def build_jars():
    """run maven build script"""
    wipedir(TF_INST_DIR)
    print 'copying touchforms code into jar resources'
    copy_pattern(os.path.join(TF_SRC_DIR, '*.py'), TF_INST_DIR)
    run('mvn package')

def get_built_jar(mode):
    """get the appropriate jar that maven built"""
    ARTIFACT_DIR = _path('target')
    jars = dict(('standalone' if 'with-dependencies' in path else 'split', path)
                for path in glob.glob(os.path.join(ARTIFACT_DIR, '*.jar')))
    return jars[mode]

def load_maven_properties():
    """get build properties used by maven script"""
    with open(_path('local.properties')) as f:
        lines = f.readlines()

    def _props():
        for ln in lines:
            if re.match(r'\s*#', ln):
                continue
            m = re.match(r'(?P<key>.*?)=(?P<val>.*)', ln)
            if not m:
                continue
            key = m.group('key').strip()
            val = m.group('val').strip()
            if not key:
                continue
            yield key, val
    return dict(_props())

def sign_jar(jar):
    """sign jar with dimagi javarosa key"""
    print 'signing %s' % jar
    props = load_maven_properties()
    props['jar'] = jar
    run('jarsigner -keystore "%(keystore.path)s" -storepass %(keystore.password)s -keypass %(keystore.password)s %(jar)s %(keystore.alias)s' % props, False)

def external_jars(distdir, fullpath=True):
    """get list of all the extra jars that offline cloudcare depends on"""
    _f = lambda path: os.path.split(path)[1]
    return [k if fullpath else _f(k) for k in
            glob.glob(os.path.join(distdir, '*.jar')) if
            not _f(k).startswith('offline-cloudcare')]

def make_jnlp(distdir, root_url):
    """create jnlp file for web start deployment"""
    print 'creating jnlp file'
    with open(_path('template.jnlp')) as f:
        template = Template(f.read())
    with open(os.path.join(distdir, 'offline-cloudcare.jnlp'), 'w') as f:
        f.write(template.render(
            url_root=root_url,
            external_jars=external_jars(distdir, False),
        ))

def package(mode, root_url):
    """package up jar (and any dependencies) for deployment via web start"""
    print 'packaging for [%s]' % mode
    DIST = os.path.join(DIST_DIR, mode)
    mkdir(DIST)
    shutil.copyfile(get_built_jar(mode), os.path.join(DIST, 'offline-cloudcare.jar'))

    if mode == 'split':
        copy_pattern(os.path.join(TF_JARS_DIR, '*.jar'), DIST)
        shutil.copy(JYTHON_JAR, DIST)
        for jar in external_jars(DIST):
            sign_jar(jar)

    make_jnlp(DIST, root_url)

def build(root_url, modes, opts):
    """main entry point"""
    wipedir(DIST_DIR)

    if not opts.nodeps:
        register_deps()
    build_jars()
    for mode in modes:
        package(mode, root_url)


if __name__ == '__main__':
    parser = OptionParser(usage='usage: %prog [options] deploy-url-root')
    parser.add_option('--nodeps', dest='nodeps', action='store_true', help='skip installing external dependencies')
    (options, args) = parser.parse_args()

    build(args[0], ['standalone', 'split'], options)

