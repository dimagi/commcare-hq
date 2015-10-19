module.exports = function(grunt) {
    var BASE_URL = 'http://localhost:8000/mocha/';

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
    ];

    var mochaConfig = {},
        watchConfig = {};

    apps.forEach(function(app) {
        mochaConfig[app] = {
            options: {
                urls: [BASE_URL + app],
                run: true
            }
        };
        watchConfig[app] = {
            files: [
                'corehq/apps/' + app + '/static/' + app + '/js/**/*.js',
                'corehq/apps/' + app + '/static/' + app + '/spec/**/*.js',
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
};
