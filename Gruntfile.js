module.exports = function(grunt) {
    // use localhost unless we're running on travis
    var BASE_ADDRESS = process.env.WEB_TEST_PORT_8000_TCP_ADDR || 'localhost',
        BASE_URL = 'http://' + BASE_ADDRESS + ':8000/mocha/';

    /*
     * To add a new app to test, add the app name to this test and create
     * a test runner view at:
     *
     * corehq/apps/<app>/templates/<app>/spec/mocha.html
     *
     * You can view an example in the app_manager
     */
    var apps = [
        'app_manager',
        'app_manager#fields',
        'export',
        'export#ko',
        'notifications',
        'reports_core#choiceListUtils',
        'locations',
        'userreports',
        'cloudcare',
        'cloudcare#form_entry',
        'hqwebapp',
        'case_importer',
    ];

    var mochaConfig = {},
        watchConfig = {};

    apps.forEach(function(app) {
        var parts = app.split('#');
        var appName = parts[0];
        var config = parts[1];

        mochaConfig[app] = {
            options: {
                urls: [BASE_URL + appName + '/' + (config ? config : '')],
                run: true,
                log: true,
                logErrors: true,
                reporter: 'Spec'
            }
        };
        watchConfig[app] = {
            files: [
                'corehq/apps/' + appName + '/static/' + appName + '/js/**/*.js',
                'corehq/apps/' + appName + '/static/' + appName + '/ko/**/*.js',
                'corehq/apps/' + appName + '/static/' + appName + '/spec/**/*.js',
            ],
            tasks: ['mocha:' + app]
        };
    });

    grunt.initConfig({
        mocha: mochaConfig,
        watch: watchConfig,
    });

    grunt.loadNpmTasks('grunt-mocha');
    grunt.loadNpmTasks('grunt-contrib-watch');
    grunt.registerTask('default', ['mocha']);
    grunt.registerTask('list', 'Lists all available apps to test', function() {
        apps.forEach(function(app) { console.log(app); });
    });
};
