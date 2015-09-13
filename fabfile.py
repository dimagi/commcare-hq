if __name__ == '__main__':
    import settings
    import sys
    from fab.pillow_settings import test_pillow_settings

    if sys.argv[1] == 'test_pillows':
        test_pillow_settings(sys.argv[2], settings.PILLOWTOPS)
else:
    from fab.fabfile import *
    from fab.chief import *

