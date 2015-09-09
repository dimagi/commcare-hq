from StringIO import StringIO
import itertools
from zipfile import ZipFile, ZIP_DEFLATED
from django.conf import settings
import shlex
from subprocess import PIPE
from tempfile import NamedTemporaryFile
import os
from dimagi.utils.subprocess_manager import subprocess_context


class JadDict(dict):
    @classmethod
    def from_jad(cls, jad_contents):
        sep = ": "
        jd = cls()
        if '\r\n' in jad_contents:
            jd.line_ending = '\r\n'
        else:
            jd.line_ending = '\n'
        lines = [line.strip() for line in jad_contents.split(jd.line_ending) if line.strip()]
        for line in lines:
            i = line.find(sep)
            if i == -1:
                pass
            key, value = line[:i], line[i+len(sep):]
            jd[key] = value
        return jd

    def render(self):
        '''Render self as jad file contents'''
        ordered_start = ['MIDlet-Name', 'MIDlet-Version', 'MIDlet-Vendor', 'MIDlet-Jar-URL',
                        'MIDlet-Jar-Size', 'MIDlet-Info-URL', 'MIDlet-1', 'MIDlet-Permissions']
        ordered_end = ['MIDlet-Jar-RSA-SHA1', 'MIDlet-Certificate-1-1',
                        'MIDlet-Certificate-1-2', 'MIDlet-Certificate-1-3',
                        'MIDlet-Certificate-1-4']
        unordered = [key for key in self.keys() if key not in ordered_start and key not in ordered_end]
        props = itertools.chain(ordered_start, sorted(unordered), ordered_end)
        lines = ['%s: %s%s' % (key, self[key], self.line_ending) for key in props if self.get(key) is not None]
        return "".join(lines)


def sign_jar(jad, jar):
    if not (hasattr(jad, 'update') and hasattr(jad, 'render')):
        jad = JadDict.from_jad(jad)

    ''' run jadTool on the newly created JAR '''
    key_store   = settings.JAR_SIGN['key_store']
    key_alias   = settings.JAR_SIGN['key_alias']
    store_pass  = settings.JAR_SIGN['store_pass']
    key_pass    = settings.JAR_SIGN['key_pass']
    jad_tool    = os.path.join(os.path.abspath(os.path.dirname(__file__)),'JadTool.jar')
    # remove traces of former jar signings, if any
    jad.update({
        "MIDlet-Certificate-1-1" : None,
        "MIDlet-Certificate-1-2" : None,
        "MIDlet-Certificate-1-3" : None,
        "MIDlet-Jar-RSA-SHA1" : None,
        "MIDlet-Permissions" : None
    })
    line_ending = jad.line_ending
    # save jad and jar to actual files
    with NamedTemporaryFile('w', suffix='.jad', delete=False) as jad_file:
        with NamedTemporaryFile('wb', suffix='.jar', delete=False) as jar_file:

            jad_file.write(jad.render())
            jar_file.write(jar)

            jad_file.flush()
            jar_file.flush()
            
            step_one = 'java -jar "%s" -addjarsig -jarfile "%s" -alias %s -keystore "%s" -storepass %s -keypass %s -inputjad "%s" -outputjad "%s"' % \
                            (jad_tool, jar_file.name, key_alias, key_store, store_pass, key_pass, jad_file.name, jad_file.name)

            step_two = 'java -jar "%s" -addcert -alias %s -keystore "%s" -storepass %s -inputjad "%s" -outputjad "%s"' % \
                            (jad_tool, key_alias, key_store, store_pass, jad_file.name, jad_file.name)

            with subprocess_context() as subprocess:
                for step in (step_one, step_two):
                    p = subprocess.Popen(shlex.split(step), stdout=PIPE, stderr=PIPE, shell=False)
                    _, stderr = p.communicate()
                    if stderr.strip():
                        raise Exception(stderr)

            with open(jad_file.name) as f:
                txt = f.read()
                jad = JadDict.from_jad(txt)
            
            try:
                os.unlink(jad_file.name)
                os.unlink(jar_file.name)
            except Exception:
                pass
    
    jad.update({
        "MIDlet-Permissions" :
            "javax.microedition.io.Connector.file.read,"
            "javax.microedition.io.Connector.ssl,"
            "javax.microedition.io.Connector.file.write,"
            "javax.microedition.io.Connector.comm,"
            "javax.microedition.io.Connector.http,"
            "javax.microedition.io.Connector.https,"
            "javax.microedition.io.Connector.sms,"
            "javax.wireless.messaging.sms.send,"
            "javax.microedition.media.control.VideoControl.getSnapshot"
    })
    jad.line_ending = line_ending

    return jad.render()


class JadJar(object):
    def __init__(self, jad, jar, version=None, build_number=None, signed=False):
        jad, jar = [j.read() if hasattr(j, 'read') else j for j in (jad, jar)]
        self._jad = jad
        self._jar = jar
        self.version = version
        self.build_number = build_number
        self.signed = signed

    @property
    def jad(self):
        return self._jad
    @property
    def jar(self):
        return self._jar

    def pack(self, files, jad_properties=None):
        jad_properties = jad_properties or {}

        # pack files into jar
        buffer = StringIO(self.jar)
        with ZipFile(buffer, 'a', ZIP_DEFLATED) as zipper:
            for path in files:
                zipper.writestr(path, files[path])
        buffer.flush()
        jar = buffer.getvalue()
        buffer.close()

        # update and sign jad
        signed = False
        if self.jad:
            jad = JadDict.from_jad(self.jad)
            jad.update({
                'MIDlet-Jar-Size': len(jar),
            })
            jad.update(jad_properties)
            if hasattr(settings, 'JAR_SIGN'):
                jad = sign_jar(jad, jar)
                signed = True
            else:
                jad = jad.render()
        else:
            jad = None

        return JadJar(jad, jar, self.version, self.build_number, signed=signed)
