/* globals process */

module.exports = function (grunt) {
    var headless = require('mocha-headless-chrome'),
        _ = require('lodash'),
        fs = require('fs');

    // use localhost unless we're running on travis
    var BASE_ADDRESS = process.env.WEB_TEST_PORT_8000_TCP_ADDR || 'localhost',
        BASE_URL = 'http://' + BASE_ADDRESS + ':8000/mocha/';

    /*
     * To run all tests:
     *    grunt test
     *
     * To run a single test:
     *    grunt test:<app>
     *
     * To add a new app to test:
     *  - Add the app name to this list
     *  - Create a test runner view at corehq/apps/<app>/templates/<app>/spec/mocha.html
     *  - Test in the browser at http://localhost:8000/mocha/<app>
     *
     * To add a new section to an existing app:
     *  - Add <app>/<section> to this list
     *  - Create a test runner view at corehq/apps/<app>/templates/<app>/spec/<section>/mocha.html
     *  - Test in the browser at http://localhost:8000/mocha/<app>/<section>
     */
    var apps = [
        'app_manager',
        'export/ko',
        'notifications',
        'reports_core/choiceListUtils',
        'locations',
        'userreports',
        'cloudcare',
        'cloudcare/form_entry',
        'hqwebapp',
        'case_importer',
    ];

    var custom = [
        'champ',
    ];

    var extensions = _.split(process.env.JS_TEST_EXTENSIONS || '', ','),
        testPaths = _.filter(_.concat(apps, custom, extensions), function (path) { return path !== ''; });

    var runTest = function (queuedTests, taskPromise, finishedTests, failures) {
        if (finishedTests === undefined) {
            finishedTests = [];
            failures = {};
        }

        if (queuedTests.length === 0) {
            if (!_.isEmpty(failures)) {
                printFailures(failures);
                grunt.fail.fatal("Javascript tests failed.");
            }
            taskPromise();
            return;
        }

        var currentApp = queuedTests[0],
            currentTestPath = BASE_URL + currentApp,
            testText = "Running Test '" + currentApp + "'",
            reporter = grunt.option('verbose') ? 'spec' : 'dot',
            runnerOptions = {
                file: currentTestPath,
                visible: false,
                timeout: 120000,
                reporter: reporter,
            };

        // For running in docker/travis
        if (process.env.PUPPETEER_SKIP_DOWNLOAD) {
            runnerOptions.executablePath = 'google-chrome-unstable';
        }

        grunt.log.writeln("\n");
        grunt.log.writeln(testText.bold);
        grunt.log.write(currentTestPath.italic.cyan);

        headless.runner(runnerOptions).then(function (data) {
            if (data.result.failures.length) {
                failures[currentApp] = data.result.failures;
            }
            if (grunt.option('coverage')) {
                var coverageDir = './coverage-js/',
                    filePath = coverageDir + currentApp.replace(/\//g, '-') + '.json';
                if (!fs.existsSync(coverageDir)) {
                    fs.mkdir(coverageDir, error =>
                        error && grunt.log.write(error));
                }
                fs.writeFile(filePath, JSON.stringify(data.coverage), { flag: 'w+' }, error =>
                    error && grunt.log.write(error)
                );
            }
            finishedTests.push(currentApp);
            runTest(
                _.without(queuedTests, currentApp),
                taskPromise,
                finishedTests,
                failures
            );
        });
    };

    var printFailures = function (failures) {
        grunt.log.writeln("\n");
        var numFailures = _.flatten(_.values(failures)).length + " test(s) failed.";
        grunt.log.writeln(numFailures.bold.red);

        _.forIn(failures, function (errors, appName) {
            grunt.log.writeln("\n");
            var failSummary = " has " + errors.length + " error(s)";
            grunt.log.write(appName.bold);
            grunt.log.writeln(failSummary.bold.red);
            _.each(errors, function (error) {
                grunt.log.write("\nERROR: ".bold.red);
                grunt.log.writeln(error.fullTitle);
                grunt.log.error(error.err.stack);
                grunt.log.write("\n");
            });
        });
    };

    grunt.task.registerTask(
        'test',
        'Runs Javascript Tests. Pass in an argument to run a specific test',
        function (arg) {
            var paths = testPaths;
            if (arg) {
                paths = [arg];
            }
            var testStatement = "Running tests: " + paths.join(', ');
            grunt.log.writeln(testStatement.bold.green);
            runTest(paths, this.async());
        }
    );

    grunt.registerTask('list', 'Lists all available apps to test', function () {
        testPaths.forEach(function (app) { console.log('"' + app + '"'); });
    });
};
