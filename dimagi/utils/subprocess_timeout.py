import subprocess
import threading

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

    def run(self, timeout=None):
        def target(*args, **kwargs):
            self.process = subprocess.Popen(*args, **kwargs)
            self.process.communicate()

        thread = threading.Thread(target=target, args=self.args, kwargs=self.kwargs)
        thread.start()

        thread.join(timeout)
        if thread.is_alive() and self.process:
            self.process.terminate()
            thread.join()
            raise ProcessTimedOut("Process `%s` timed out after %s seconds" % (
                ' '.join(self.args[0] if self.args else self.kwargs.get('args')),
                timeout
            ))
        elif self.process is None:
            raise ProcessTimedOut("Process `%s` timed out after %s seconds before even getting a chance to start" % (
                ' '.join(self.args[0] if self.args else self.kwargs.get('args')),
                timeout
            ))
        else:
            return self.process.returncode