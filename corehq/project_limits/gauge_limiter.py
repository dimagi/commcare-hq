from dataclasses import dataclass


@dataclass
class GaugeLimiter:

    gauge: 'Gauge'
    max_threshold: int
    avg_threshold: int

    def wait(self):
        pass

    def report(self, scope, value):
        self.gauge.report(scope, value)


@dataclass
class Gauge:
    scopes: tuple[str]
    timeout: int

    def report(self, scope, value):
        pass
