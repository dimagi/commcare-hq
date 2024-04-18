import sys


def create_nose_virtual_package():
    sys.modules['nose.tools'] = VirtualNose.tools
    sys.modules['nose.plugins.attrib'] = VirtualNose.plugins.attrib


class VirtualNose:
    """Legacy namespace for tests written before pytest"""
    class tools:
        def nottest(fn):
            fn.__test__ = False
            return fn

    class plugins:
        class attrib:
            def attr(*args, **kwargs):
                # TODO adapt to pytest
                """Decorator that adds attributes to classes or functions
                for use with the Attribute (-a) plugin.
                """
                def wrap_ob(ob):
                    for name in args:
                        setattr(ob, name, True)
                    for name, value in kwargs.items():
                        setattr(ob, name, value)
                    return ob
                return wrap_ob
