import sys
sys.path.insert(0, '__pyclasspath__/Lib') # 'Lib' seems magic somehow; don't use any other directory name

sys.prefix = '' # fix issue with optparse

from touchforms import xformserver
xformserver.main(stale_window=0.1, offline=True)

