import StringIO
from optparse import make_option
import shutil
import os
from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = "Compiles all the files necessary for the UI of CommCare HQ from HQ Bootstrap. Make sure lessc and uglifyjs are installed"
    root_dirs = ["css",
                 "js",
                 "img"]
    less_files = ["hq-bootstrap",
                  "old/core",
                  "old/app_manager",
                  "mobile_c2/hq-mobile-c2"]
    js_bootstrap = ["bootstrap-transition",
                    "bootstrap-affix",
                    "bootstrap-alert",
                    "bootstrap-button",
                    "bootstrap-carousel",
                    "bootstrap-collapse",
                    "bootstrap-dropdown",
                    "bootstrap-modal",
                    "bootstrap-tooltip",
                    "bootstrap-popover",
                    "bootstrap-scrollspy",
                    "bootstrap-tab",
                    "bootstrap-typeahead",
                    "plugins/bootstrap-combobox"]

    bootstrap_source = "submodules/hq-bootstrap"
    bootstrap_destination = "submodules/core-hq-src/corehq/apps/hq_bootstrap/static/hq_bootstrap"

    formdesigner_dest = "submodules/formdesigner"

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

        if "vellum" in args:
            self.bootstrap_destination = "submodules/formdesigner/hq-bootstrap-standalone"

        # make sure all of the root dirs exist
        for root_dir in self.root_dirs:
            full_root_dir = os.path.join(self.bootstrap_destination, root_dir)
            try:
                os.makedirs(full_root_dir)
            except OSError:
                print "%s was already created. Cleaning it up." % full_root_dir
                self.clear_dir(full_root_dir)

        # copy files over from hq-bootstrap
        self.copy_all_files("js/includes", "js")
        self.copy_all_files("img")

        # compile all of the less files
        self.prepare_dir(self.less_files, "css")
        for less_file in self.less_files:
            self.compile_file(self.lessc,
                                os.path.join(self.bootstrap_source, "less/%s.less" % less_file),
                                os.path.join(self.bootstrap_destination, "css/%s.css" % less_file))

        for fd_less in ["formdesigner", "screen"]:
            self.compile_file(self.lessc,
                                os.path.join(self.bootstrap_source, "less/formdesigner-old/%s.less" % fd_less),
                                os.path.join(self.formdesigner_dest, "css/%s.css" % fd_less))

        # cat and minify the bootstrap javascript files
        complete_bootstrap = open(os.path.join(self.bootstrap_destination, "js/bootstrap.js"), "w+")
        for js_file in self.js_bootstrap:
            filestring = open(os.path.join(self.bootstrap_source, "js/%s.js" % js_file), "r").read()
            complete_bootstrap.write(filestring)
            complete_bootstrap.write("\n")
        complete_bootstrap.close()

        self.compile_file(self.uglifyjs,
                        os.path.join(self.bootstrap_destination, "js/bootstrap.js"),
                        os.path.join(self.bootstrap_destination, "js/bootstrap.min.js"))


    def compile_file(self, command, source, dest):
        compile_command = "%(command)s %(source)s > %(dest)s" %\
                            {"command": command,
                             "source": source,
                             "dest": dest}
        print compile_command
        os.system(compile_command)


    def copy_all_files(self, folder_nub, folder_nub_dest=None):
        folder_src = os.path.join(self.bootstrap_source, folder_nub)
        if folder_nub_dest:
            folder_dest = os.path.join(self.bootstrap_destination, folder_nub_dest)
        else:
            folder_dest = os.path.join(self.bootstrap_destination, folder_nub)

        if not os.path.exists(folder_dest):
            try:
                os.mkdir(folder_dest)
            except OSError:
                print "Could not create directory %s." % folder_dest
        else:
            self.clear_dir(folder_dest)

        for the_file in os.listdir(folder_src):
            file_src = os.path.join(folder_src, the_file)
            file_dest = os.path.join(folder_dest, the_file)
            try:
                if os.path.isfile(file_src):
                    shutil.copy(file_src, file_dest)
                else:
                    if folder_nub_dest:
                        self.copy_all_files("%s/%s" % (folder_nub, the_file), "%s/%s" % (folder_nub_dest, the_file))
                    else:
                        self.copy_all_files("%s/%s" % (folder_nub, the_file))
            except OSError:
                print "Could not handle copying file from %s to %s." % (file_src, file_dest)

    def clear_dir(self, folder):
        for the_file in os.listdir(folder):
            file_path = os.path.join(folder, the_file)
            try:
                if os.path.isfile(file_path):
                    os.remove(file_path)
            except OSError:
                print "Could not remove file at path %s." % file_path


    def prepare_dir(self, file_list, root_dir):
        created_dirs = []
        for file in file_list:
            structure = file.split("/")
            if len(structure) > 1:
                directory = "/".join(structure[0:-1])
                if not directory in created_dirs:
                    created_dirs.append(directory)
                    new_dir = os.path.join(self.bootstrap_destination, "%s/%s" % (root_dir, directory))
                    if not os.path.exists(new_dir):
                        try:
                            os.makedirs(new_dir)
                        except OSError:
                            print "Could not make directory %s." % new_dir
                    else:
                        self.clear_dir(new_dir)
