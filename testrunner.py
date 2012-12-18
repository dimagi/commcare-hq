from couchdbkit.ext.django.testrunner import CouchDbKitTestSuiteRunner
from django.conf import settings
import settingshelper

class HqTestSuiteRunner(CouchDbKitTestSuiteRunner):
    """
    A test suite runner for Hq.  On top of the couchdb testrunner, also
    apply all our monkeypatches to the settings.
    
    To use this, change the settings.py file to read:
    
    TEST_RUNNER = 'Hq.testrunner.HqTestSuiteRunner'
    """
    
    dbs = []
    def setup_test_environment(self, **kwargs):
        # monkey patch TEST_APPS into INSTALLED_APPS so that tests are run for them
        # without having to explicitly have them in INSTALLED_APPS
        # weird list/tuple type issues, so force everything to tuples
        settings.INSTALLED_APPS = tuple(settings.INSTALLED_APPS) + tuple(settings.TEST_APPS)
        return super(HqTestSuiteRunner, self).setup_test_environment(**kwargs)
        
    def setup_databases(self, **kwargs):
        self.newdbname = self.get_test_db_name(settings.COUCH_DATABASE_NAME)
        print "overridding the couch settings!"
        new_db_settings = settingshelper.get_dynamic_db_settings(settings.COUCH_SERVER_ROOT, 
                                                                 settings.COUCH_USERNAME, 
                                                                 settings.COUCH_PASSWORD, 
                                                                 self.newdbname, 
                                                                 settings.INSTALLED_APPS)
        settings.COUCH_DATABASE_NAME = self.newdbname
        for (setting, value) in new_db_settings.items():
            setattr(settings, setting, value)
            print "set %s settting to %s" % (setting, value)

        return super(HqTestSuiteRunner, self).setup_databases(**kwargs)
