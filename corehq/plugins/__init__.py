from corehq.plugins.signal_plugin import SignalPlugins

plugin_manager = SignalPlugins()

register_extension_point = plugin_manager.register_extension_point
register_plugin = plugin_manager.register_plugin
get_contributions = plugin_manager.get_extension_point_contributions
