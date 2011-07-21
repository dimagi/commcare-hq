import sys, os

"""
Checks for the existence of files against a static list of filenames.

Prints out any missing files, or reports "passing"
"""

class FileChecker(object):
    COMMANDS = {
        "?": "help",
        "r": "run_file_check",
        "l": "list_extras",
        "q": "quit",
        "c": "clean",
    }
    
    EXCLUDES = set(("commcare.jad", "commcare.jar", "checkfiles.py", "list.txt"))
        
    def __init__(self, filepath, list):
        self._setfilepath(filepath)
        self._setlist(list)
        
    def _setlist(self, list):
        if not os.path.exists(list):
            print "no such file %s" % list
        else:
            print "using file list: %s" % list
            self.list = list

    def _setfilepath(self, path):
        if not os.path.exists(path):
            print "no such file %s" % path
        else:
            print "searching in %s" % path
            self.path = path
    
    def get_filelist(self):
        with open(self.list, "r") as list_file:
            return [line.strip() for line in list_file if line.strip()]
    
    def run_file_check(self):
        """
        Checks the list against the directory for any missing files
        """
        if not os.path.exists(self.list):
            raise Exception("No such list file: %s" % self.list)
        
        missing = []
        searched = []
        for filename in self.get_filelist():
            
            searched.append(filename)
            fileparts = filename.split("/")
            expected_file = os.path.join(self.path, *fileparts)
            if not os.path.exists(expected_file):
                missing.append(filename)
        
        missing = set(missing)
        searched = set(searched)
        if missing:
            print "FAILED! %s files are missing:" % len(missing)
            print "==============================="
            print "\n".join(sorted(missing))
            
        else:
            print "Pass. All %s files found" % len(searched)

        self.next()
        
    def searchdir(self):
        def _inner_search(dir, prefix, l, sep="/"):
            for f in os.listdir(dir):
                if f.startswith("."): continue # skip hidden files
                if os.path.isdir(os.path.join(dir, f)):
                    _inner_search(os.path.join(dir, f), "%s%s%s" % (prefix, f, sep), l, sep)
                else: 
                    l.append("%s%s" % (prefix,f))
        
        ret = []
        _inner_search(self.path, "", ret)
        return ret
    
    def get_extras(self):
        full_filelist = set([f.lower() for f in self.searchdir()]) - self.EXCLUDES
        expected = set([f.lower() for f in self.get_filelist()])
        return full_filelist - expected
        
    def list_extras(self):
        """
        List all files found in the directory that aren't AREN'T in the list
        """
        extras = self.get_extras()
        if extras:
            print "==============================="
            print "\n".join(sorted(extras))
            print "Found %s extra files:" % len(extras)
            
        else:
            print "==============================="
            print "Passed! No extra files."
        self.next()
            
    def clean(self):
        """
        Clean (Remove all files in the directory not found in the list)
        """
        extras = self.get_extras()
        print "Excluding %s from deletion" % ", ".join(self.EXCLUDES)
        input = raw_input("Really delete %s extra files this is NOT REVERSIBLE? ('y' to proceed)\n" % len(extras)).lower()
        if input == "y":
            for f in extras:
                fileparts = f.split("/")
                expected_file = os.path.join(self.path, *fileparts)
                if os.path.exists(expected_file):
                    os.unlink(expected_file)
            print "cleaned all files" 
            
        else:
            print "aborted."
        
        self.next()
            
            
    def help(self):
        """
        Print a list of commands.
        """
        print "Available commands:"
        print "\n".join("%s: %s" % (cmd, getattr(self, func).__doc__.strip()) \
                        for cmd, func in self.COMMANDS.items())
        self.next()
        
    
    def quit(self):
        """
        Exit.
        """
        sys.exit()
    
    def next(self):
        print "==============================="
        input = raw_input("\nwhat's next? Enter '?' for help.\n", ).lower()
        if input in self.COMMANDS:
            getattr(self, self.COMMANDS[input])()
        else:
            print "sorry, unknown command %s"
            self.help()
    
    
if __name__=='__main__':
    loc = os.path.abspath(os.path.dirname(__file__))
    file_path = sys.argv[1] if len(sys.argv) > 1 else loc
    file_list = sys.argv[2] if len(sys.argv) > 2 else os.path.join(file_path, "list.txt")
    fc = FileChecker(file_path, file_list)
    fc.next()
