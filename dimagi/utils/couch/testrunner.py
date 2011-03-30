import sys
from django.test.simple import DjangoTestSuiteRunner
from django.conf import settings
from couchdbkit.ext.django import loading as loading
from couchdbkit.resource import ResourceNotFound

class CouchDbKitTestSuiteRunner(DjangoTestSuiteRunner):
    """
    A test suite runner for couchdbkit.  This offers the exact same functionality
    as the default django test suite runner, except that it connects all the couchdbkit
    django-extended models to a test database.  The test database is deleted at the
    end of the tests.  To use this, just add this file to your project and the following 
    line to your settings.py file:
    
    TEST_RUNNER = 'myproject.testrunner.CouchDbKitTestSuiteRunner'
    """
    
    dbs = []
    
    def get_test_db_name(self, dbname):
        return "%s_test" % dbname
        
    def setup_databases(self, **kwargs):
        print "overridding the couchdbkit database settings to use a test database!"
                 
        # first pass: just implement this as a monkey-patch to the loading module
        # overriding all the existing couchdb settings
        self.dbs = [(app, self.get_test_db_name(url)) for app, url in getattr(settings, "COUCHDB_DATABASES", [])]
        settings.COUCH_DATABASE = self.get_test_db_name(settings.COUCH_DATABASE)
        old_handler = loading.couchdbkit_handler
        couchdbkit_handler = loading.CouchdbkitHandler(self.dbs)
        loading.couchdbkit_handler = couchdbkit_handler
        loading.register_schema = couchdbkit_handler.register_schema
        loading.get_schema = couchdbkit_handler.get_schema
        loading.get_db = couchdbkit_handler.get_db

        #if couchforms exists, monkey patch the XFORMS_POST_URL
        for app, url in self.dbs:
            if app == "couchforms":
                settings.XFORMS_POST_URL = "%s/_design/couchforms/_update/xform/" % (url)
                break

        # register our dbs with the extension document classes
        for app, value in old_handler.app_schema.items():
            for name, cls in value.items():
                cls.set_db(loading.get_db(app))
                                
                
        return super(CouchDbKitTestSuiteRunner, self).setup_databases(**kwargs)
    
    def teardown_databases(self, old_config, **kwargs):
        deleted_databases = []
        skipcount = 0
        for app, item in self.dbs:
            app_label = app.split('.')[-1]
            db = loading.get_db(app_label)
            if db.dbname in deleted_databases: 
                skipcount += 1
                continue
            try:
                db.server.delete_db(db.dbname)
                deleted_databases.append(db.dbname)
                print "deleted database %s for %s" % (db.dbname, app_label)
            except ResourceNotFound:
                print "database %s not found for %s! it was probably already deleted." % (db.dbname, app_label)
        if skipcount:
            print "skipped deleting %s app databases that were already deleted" % skipcount
        return super(CouchDbKitTestSuiteRunner, self).teardown_databases(old_config, **kwargs)

try:

    import xmlrunner
    from django.test.simple import *
    class CouchDbKitXMLTestSuiteRunner(CouchDbKitTestSuiteRunner):
        def __init__(self, *args, **kwargs):
            CouchDbKitTestSuiteRunner.__init__(self)

        def setup_databases(self, **kwargs):
            return CouchDbKitTestSuiteRunner.setup_databases(self, **kwargs)
            #return super(CouchDbKitXMLTestSuiteRunner, self).setup_databases(**kwargs)
        def teardown_databases(self, old_config, **kwargs):
            #return super(CouchDbKitXMLTestSuiteRunner, self).teardown_databases(old_config, **kwargs)
            return CouchDbKitTestSuiteRunner.teardown_databases(self, old_config, **kwargs)

        def run_tests(self, test_labels, verbosity=1, interactive=True, extra_tests=[]):
            """
            adapted from xmlrunner.extra.djangotestrunner.run_tests
            """
            self.setup_test_environment()

            settings.DEBUG = False

            verbose = getattr(settings, 'TEST_OUTPUT_VERBOSE', False)
            descriptions = getattr(settings, 'TEST_OUTPUT_DESCRIPTIONS', False)
            output = getattr(settings, 'TEST_OUTPUT_DIR', '.')

            suite = self.build_suite(test_labels, extra_tests) #unittest.TestSuite()
            old_config=self.setup_databases()
            result = xmlrunner.XMLTestRunner(verbose=verbose, descriptions=descriptions, output=output).run(suite)

            self.teardown_databases(old_config)
            self.teardown_test_environment()
            return len(result.failures) + len(result.errors)
            #return self.suite_result(suite, result)


except:
    pass
