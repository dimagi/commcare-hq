import StringIO
from optparse import make_option
import shutil
import os
from django.core.management.base import BaseCommand

class Command(BaseCommand):
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
        "timepicker",
    ]

    hqstyle_src = "corehq/apps/style/"
    hq_bootstrap_src = "%s/static/style/lib/bootstrap" % hqstyle_src
    font_awesome_src = "%s/static/style/lib/fontawesome" % hqstyle_src
    destination = "%s/static/style/lib/bootstrap2" % hqstyle_src

    lessc = "lessc"
    uglifyjs = "uglifyjs"

    def handle(self, *args, **options):
        print "\nBUILDING HQ BOOTSTRAP\n"
        # some options to handle running commands directly from opt in the case of aliasing problems
        if "direct-lessc" in args and "node" in args:
            self.lessc = "node /opt/lessc/bin/lessc"
            print "NOTICE: Using lessc as '%s'" % self.lessc
        elif "direct-lessc" in args:
            self.lessc = "nodejs /opt/lessc/bin/lessc"
            print "NOTICE: Using lessc as '%s'" % self.lessc

        if "direct-uglifyjs" in args:
            self.uglifyjs = "/opt/UglifyJS/bin/uglifyjs"
            print "NOTICE: Using uglifyjs as '%s'" % self.uglifyjs

        self.compile_core_js()
        self.copy_bootstrap_images()
        self.copy_font_awesome()

    def compile_core_js(self):
        print "\nCompiling HQStyle Core Javascript"
        core_dest = "%s/js/core" % self.destination
        all_js = open(os.path.join(core_dest, "bootstrap.js"), "w+")
        print "-- HQ Bootstrap ----"
        self.concat_files(all_js, self.js_bootstrap, self.hq_bootstrap_src, "js/bootstrap-%s.js")
        print "-- HQ Style ----"
        self.concat_files(all_js, self.js_plugins, self.hqstyle_src, "static/style/js/bootstrap-%s.js")
        all_js.close()

        self.compile_file(self.uglifyjs,
            os.path.join(core_dest, "bootstrap.js"),
            os.path.join(core_dest, "bootstrap.min.js"))

    def concat_files(self, all_files, file_names, source_dir, file_pattern):
        for f in file_names:
            print f
            filestring = open(os.path.join(source_dir, file_pattern % f), "r").read()
            all_files.write(filestring)
            all_files.write("\n")

    def copy_bootstrap_images(self):
        print "\nCopying Images from HQ Bootstrap"
        source_folder = "%s/img" % self.hq_bootstrap_src
        dest_folder = "%s/img" % self.destination
        self.copy_all_files(source_folder, dest_folder)

    def copy_font_awesome(self):
        print "\nCopying fonts for Font Awesome"
        source_folder = "%s/font" % self.font_awesome_src
        dest_folder = "%s/css/font" % self.destination
        self.copy_all_files(source_folder, dest_folder)

    def copy_all_files(self, folder_src, folder_dest):
        for the_file in os.listdir(folder_src):
            file_src = os.path.join(folder_src, the_file)
            file_dest = os.path.join(folder_dest, the_file)
            try:
                if os.path.isfile(file_src):
                    shutil.copy(file_src, file_dest)
                    print "copied %s" % the_file
            except OSError:
                print "Could not handle copying file from %s to %s." % (file_src, file_dest)

    def compile_file(self, command, source, dest):
        print "Running Command:"
        compile_command = "%(command)s %(source)s > %(dest)s" %\
                          {"command": command,
                           "source": source,
                           "dest": dest}
        print compile_command
        os.system(compile_command)
