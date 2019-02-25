module.exports = function(grunt) {
    // use localhost unless we're running on travis
    var BASE_ADDRESS = process.env.WEB_TEST_PORT_8000_TCP_ADDR || 'localhost',
        BASE_URL = 'http://' + BASE_ADDRESS + ':8000/mocha/';

    /*
     * To add a new app to test:
     *  - Add the app name to this list
     *  - Create a test runner view at corehq/apps/<app>/templates/<app>/spec/mocha.html
     *  - Test in the browser at http://localhost:8000/mocha/<app>
     *
     * To add a new section to an existing app:
     *  - Add <app>#<section> to this list
     *  - Create a test runner view at corehq/apps/<app>/templates/<app>/spec/<section>/mocha.html
     *  - Test in the browser at http://localhost:8000/mocha/<app>/<section>
     */
    var apps = [
        'app_manager',
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

    var customApps = [
        'icds_reports',
        'champ',
        'aaa'
    ];

    var mochaConfig = {},
        watchConfig = {};

    var addToConfig = function(path) {
        return function (app) {
            var parts = app.split('#');
            var appName = parts[0];
            var config = parts[1];

            mochaConfig[app] = {
                options: {
                    urls: [BASE_URL + appName + '/' + (config ? config : '')],
                    run: true,
                    log: true,
                    logErrors: true,
                    reporter: 'Spec',
                },
            };
            watchConfig[app] = {
                files: [
                    path + appName + '/static/' + appName + '/js/**/*.js',
                    path + appName + '/static/' + appName + '/ko/**/*.js',
                    path + appName + '/static/' + appName + '/spec/**/*.js',
                ],
                tasks: ['mocha:' + app],
            };
        };
    };

    apps.forEach(addToConfig('corehq/apps'));
    customApps.forEach(addToConfig('custom/apps'));

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
