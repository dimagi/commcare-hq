#From https://github.com/django-extensions/django-extensions
#Copyright (c) 2007 Michael Trier
#
#Permission is hereby granted, free of charge, to any person obtaining a copy
#of this software and associated documentation files (the "Software"), to deal
#in the Software without restriction, including without limitation the rights
#to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
#copies of the Software, and to permit persons to whom the Software is
#furnished to do so, subject to the following conditions:
#
#The above copyright notice and this permission notice shall be included in
#all copies or substantial portions of the Software.
#
#THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
#IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
#FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
#AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
#LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
#OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
#THE SOFTWARE.


from django.core.management.base import BaseCommand
from django.core.management.color import no_style
from optparse import make_option
import sys
import os

try:
    set
except NameError:
    from sets import Set as set   # Python 2.3 fallback

class Command(BaseCommand):
    option_list = BaseCommand.option_list + (
        make_option('--fixtures', action='store_true', dest='infixtures', default=False,
            help='Only look in app.fixtures subdir'),
        make_option('--noscripts', action='store_true', dest='noscripts', default=False,
            help='Look in app.scripts subdir'),
        make_option('-s', '--silent', action='store_true', dest='silent', default=False,
            help='Run silently, do not show errors and tracebacks'),
        make_option('--no-traceback', action='store_true', dest='no_traceback', default=False,
            help='Do not show tracebacks'),
    )
    help = 'Runs a script in django context.'
    args = "script [script ...]"

    def handle(self, *scripts, **options):
        from django.db.models import get_apps
        
        NOTICE = self.style.SQL_TABLE
        NOTICE2 = self.style.SQL_FIELD
        ERROR = self.style.ERROR
        ERROR2 = self.style.NOTICE

        subdirs = []

        if not options.get('noscripts'):
            subdirs.append('scripts')
        if options.get('infixtures'):
            subdirs.append('fixtures')
        verbosity = int(options.get('verbosity', 1))
        show_traceback = options.get('traceback', True)
        if show_traceback is None:
            # XXX: traceback is set to None from Django ?
            show_traceback = True
        no_traceback = options.get('no_traceback', False)
        if no_traceback:
            show_traceback = False
        silent = options.get('silent', False)
        if silent:
            verbosity = 0

        if len(subdirs) < 1:
            print NOTICE("No subdirs to run left.")
            return

        if len(scripts) < 1:
            print ERROR("Script name required.")
            return

        def run_script(mod):
            # TODO: add arguments to run
            try:
                mod.run()
            except Exception, e:
                if silent:
                    return
                if verbosity > 0:
                    print ERROR("Exception while running run() in '%s'" % mod.__name__)
                if show_traceback:
                    raise
        
        def my_import(mod):
            if verbosity > 1:
                print NOTICE("Check for %s" % mod)
            try:
                t = __import__(mod, [], [], [" "])
                #if verbosity > 1:
                #    print NOTICE("Found script %s ..." % mod)
                if hasattr(t, "run"):
                    if verbosity > 1:
                        print NOTICE2("Found script '%s' ..." % mod)
                    #if verbosity > 1:
                    #    print NOTICE("found run() in %s. executing..." % mod)
                    return t
                else:
                    if verbosity > 1:
                        print ERROR2("Find script '%s' but no run() function found." % mod)
            except ImportError:
                return False
        
        def find_modules_for_script(script):
            """ find script module which contains 'run' attribute """
            modules = []
            # first look in apps
            for app in get_apps():
                app_name = app.__name__.split(".")[:-1] # + ['fixtures']
                for subdir in subdirs:
                    mod = my_import(".".join(app_name + [subdir, script]))
                    if mod:
                        modules.append(mod)

            # try app.DIR.script import
            sa = script.split(".")
            for subdir in subdirs:
                nn = ".".join(sa[:-1] + [subdir, sa[-1]])
                mod = my_import(nn)
                if mod:
                    modules.append(mod)

            # try direct import
            if script.find(".") != -1:
                mod = my_import(script)
                if mod:
                    modules.append(mod)
            
            return modules
        
        for script in scripts:
            modules = find_modules_for_script(script)
            if not modules:
                if verbosity>0 and not silent:
                    print ERROR("No module for script '%s' found" % script)
            for mod in modules:
                if verbosity>1:
                    print NOTICE2("Running script '%s' ..." % mod.__name__)
                run_script(mod)

# Backwards compatibility for Django r9110
if not [opt for opt in Command.option_list if opt.dest=='verbosity']:
    Command.option_list += (
        make_option('--verbosity', '-v', action="store", dest="verbosity",
                    default='1', type='choice', choices=['0', '1', '2'],
                    help="Verbosity level; 0=minimal output, 1=normal output, 2=all output"),
    )
