"""
Bundle and minify bootstrap JS and compile Less into CSS.

collectstatic must be run before, and make_hqstyle should only touch files in
STATIC_ROOT -- it should NOT create or modify source files.

If you find yourself wanting to add more complexity here, it's probably a sign
that we should adopt a serious asset management system like django-compressor
or django-pipeline.
"""
import os
import re
from django.contrib.staticfiles.management.commands import collectstatic
from django.conf import settings

from corehq.apps.hqwebapp.templatetags.hq_shared_tags import less

class Command(collectstatic.Command):
    help = "Compiles all the files necessary for the UI of CommCare HQ from HQ Bootstrap. Make sure lessc and uglifyjs are installed"

    # NOTE: Order matters for the bootstrap js files.
    js_bootstrap = [
        "transition",
        "alert",
        "button",
        "carousel",
        "collapse",
        "dropdown",
        "modal",
        "tooltip",
        "popover",
        "scrollspy",
        "tab",
        "typeahead",
        "affix",
    ]
    
    js_plugins = [
        "combobox",
        "multi-typeahead",
        "hoverdropdown",
        "popout",
    ]

    js_files = [
        os.path.join(settings.STATIC_ROOT, 'hq-bootstrap', 'js',
            'bootstrap-%s.js') % f for f in js_bootstrap
    ] + [
        os.path.join(settings.STATIC_ROOT, 'hqstyle', 'js', '_plugins',
            'bootstrap-%s.js') % f for f in js_plugins
    ]

    def handle_noargs(self, **options):
        super(Command, self).handle_noargs(**options)
        self.compile_core_js()
        self.compile_css()

    def compile_core_js(self):
        # This still requires you to recompile to see any changes in plugin
        # files.  Should switch to django-compressor or something similar to
        # avoid that.
        print "Compiling HQ Bootstrap JS..."

        core_dest = os.path.join(settings.STATIC_ROOT, 'hqstyle', 'js', 'core')

        if not os.path.exists(core_dest):
            os.makedirs(core_dest)

        self.compile_file("uglifyjs", " ".join(self.js_files),
                os.path.join(settings.STATIC_ROOT, 'hqstyle', 'js', 'core',
                    'bootstrap-plugins.min.js'))

    def compile_css(self):
        print "\nCompiling CSS from less template-tag references..."

        # Can switch to django-compressor or something similar in the future if
        # we need more robustness here.  Tried to use re.X but it didn't work.
        pattern = re.compile(
            "{%%\s*%s\s+(?:'|\")(?P<file>[^'\"]+)(?:'|\")" %
            less.__name__)
        less_references = set()

        for root, dirs, files in os.walk('.'):
            if 'templates' not in root:
                continue
           
            for file in files:
                with open(os.path.join(root, file)) as f:
                    for matchobj in re.finditer(pattern, f.read()):
                        less_references.add(matchobj.group('file'))
        
        for less_file in less_references:
            css_file = less_file.replace("/less/", "/css/")
            css_file = re.sub("\.less$", ".css", css_file)

            css_file_dir = os.path.join(
                settings.STATIC_ROOT, os.path.dirname(css_file))
            if not os.path.exists(css_file_dir):
                os.makedirs(css_file_dir)
            
            self.compile_file("lessc",
                os.path.join(settings.STATIC_ROOT, less_file),
                os.path.join(settings.STATIC_ROOT, css_file))

    def compile_file(self, command, source, dest):
        compile_command = "%(command)s %(source)s > %(dest)s" %\
                          {"command": command,
                           "source": source,
                           "dest": dest}
        print compile_command
        os.system(compile_command)
