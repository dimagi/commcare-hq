import time


class Timer(object):
    def __init__(self, name):
        self.name = name
        self.beginning = None
        self.end = None
        self.subs = []

    def start(self):
        self.beginning = time.time()

    def stop(self):
        self.end = time.time()

    def append(self, timer):
        self.subs.append(timer)

    @property
    def duration(self):
        if self.beginning and self.end:
            return self.end - self.beginning

    def to_dict(self):
        return {
            'name': self.name,
            'duration': self.duration,
            'subs': [sub.to_dict() for sub in self.subs]
        }

    def __repr__(self):
        print 'Timer(name={}, beginning={}, end={})'.format(self.name, self.beginning, self.end)


class TimingContext(object):
    def __init__(self , name):
        self.timings = {}
        self.root = Timer(name)
        self.stack = [self.root]

    def __call__(self, name):
        timer = Timer(name)
        current = self.peek()
        current.append(timer)
        self.stack.append(timer)
        return self

    def peek(self):
        return self.stack[len(self.stack) - 1]

    def __enter__(self):
        self.peek().start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        timer = self.stack.pop()
        timer.stop()

    def to_dict(self):
        return self.root.to_dict()
