import os
import tempfile
from os.path import exists, join
from uuid import uuid4

def check(path):
    print("exists({}) -> {}".format(path, exists(path)))
    if exists(path):
        filepath = join(path, uuid4().hex)
        try:
            with open(filepath, "w") as fh:
                fh.write("something")
            os.remove(filepath)
            print("write success: {}".format(filepath))
        except Exception as err:
            print("cannot write {}: {}".format(filepath, err))
    print("")

print("tempfile.tempdir -> {!r}".format(tempfile.tempdir))
print("tempfile.gettempdir() -> %s" % tempfile.gettempdir())
print("")

check("/tmp")
check("/home/travis/tmp")
if tempfile.gettempdir() not in ["/tmp", "/home/travis/tmp"]:
    check(tempfile.gettempdir())
