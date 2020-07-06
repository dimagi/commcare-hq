from django.dispatch import Signal

from corehq.plugins.interface import Plugins, ExtensionPoint
from dimagi.utils.logging import log_signal_errors


class PluginContribution:
    def __init__(self, delegate):
        self.delegate = delegate

    def __call__(self, signal, sender, **kwargs):
        # drop signal and sender
        return self.delegate(**kwargs)


class SignalPlugins(Plugins):
    """Plugin implementation that uses Django signals to manage the
    dispatching of extension point events
    """
    def __init__(self):
        super().__init__()
        self._signals = {}

    def connect_extension_points(self, plugin):
        for point_name, signal in self._signals.items():
            if hasattr(plugin, point_name):
                signal.connect(PluginContribution(getattr(plugin, point_name)), weak=False)

    def register_extension_point(self, point: ExtensionPoint):
        super().register_extension_point(point)
        self._signals[point.name] = Signal(providing_args=point.providing_args)

    def get_extension_point_contributions(self, extension_point, **kwargs):
        point = self.extension_point_registry[extension_point]
        signal = self._signals[extension_point]
        results = signal.send_robust(sender=point, **kwargs)
        return self.get_filter_and_log_errors(extension_point, results)

    def get_filter_and_log_errors(self, extension_point, results):
        log_signal_errors(results, f"Error gettings plugin contributions for {extension_point} %s", None)
        return [response for receiver, response in results if response is not None and not isinstance(response, Exception)]
