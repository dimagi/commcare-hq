import subprocess
import threading
import time

class ProcessTimedOut(Exception):
    pass

class Subprocess(object):
    """
    Enables to run subprocess commands in a different thread
    with TIMEOUT option!

    Based on https://gist.github.com/1306188 which is in turn
    > Based on jcollado's solution:
    > http://stackoverflow.com/questions/1191374/subprocess-with-timeout/4825933#4825933
    """
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        self.process = None

    @property
    def command_display(self):
        return ' '.join(self.args[0] if self.args else self.kwargs.get('args'))

    def run(self, timeout=None):
        def target(*args, **kwargs):
            self.process = 'started'
            self.process = subprocess.Popen(*args, **kwargs)
            self.process.communicate()
        thread = threading.Thread(target=target, args=self.args, kwargs=self.kwargs)
        thread.start()
        start = time.time()
        thread.join(timeout)
        if thread.is_alive():
            self.process.terminate()
            thread.join()
            raise ProcessTimedOut("Process `%s` timed out after %s seconds" % (
                self.command_display,
                timeout
            ))
        elif self.process == 'started':
            raise ProcessTimedOut((
                "Still don't know what's going on here. "
                "Process `%s` 'timed out' after %s seconds "
                "(not %s) with the value 'started'"
            ) % (
                self.command_display,
                time.time() - start,
                timeout,
            ))
        else:
            return self.process.returncode