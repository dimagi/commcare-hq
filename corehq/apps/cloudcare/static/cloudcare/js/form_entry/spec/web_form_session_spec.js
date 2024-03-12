'use strict';
/* global affix */
/* eslint-env mocha */
hqDefine("cloudcare/js/form_entry/spec/web_form_session_spec", [
    "sinon/pkg/sinon",
    "hqwebapp/js/initial_page_data",
    "cloudcare/js/form_entry/const",
    "cloudcare/js/form_entry/errors",
    "cloudcare/js/form_entry/form_ui",
    "cloudcare/js/form_entry/spec/fixtures",
    "cloudcare/js/form_entry/task_queue",
    "cloudcare/js/form_entry/utils",
    "cloudcare/js/form_entry/web_form_session",
    //"jasmine-fixture/dist/jasmine-fixture",     // affix - TODO: this errors in a try
], function (
    sinon,
    initialPageData,
    constants,
    errors,
    formUI,
    Fixtures,
    taskQueue,
    Utils,
    webFormSession
) {
    describe('WebForm', function () {
        before(function () {
            initialPageData.register("toggles_dict", {
                WEB_APPS_ANCHORED_SUBMIT: false,
                USE_PROMINENT_PROGRESS_BAR: false,
            });
        });

        after(function () {
            initialPageData.unregister("toggles_dict");
        });

        describe('TaskQueue', function () {
            var callCount,
                flag,
                queue = taskQueue.TaskQueue(),
                promise1,
                promise2,
                updateFlag = function (newValue, promise) {
                    flag = newValue;
                    callCount++;
                    return promise;
                };

            beforeEach(function () {
                flag = undefined;
                callCount = 0;

                promise1 = new $.Deferred(),
                promise2 = new $.Deferred();
                queue.addTask('updateFlag', updateFlag, ['one', promise1]);
                queue.addTask('updateFlag', updateFlag, ['two', promise2]);
            });

            it('Executes tasks in order', function () {
                // First task should have been executed immediately
                assert.equal(flag, "one");
                assert.equal(callCount, 1);

                // Second task should execute when first one is resolved
                promise1.resolve();
                assert.equal(flag, "two");
                assert.equal(callCount, 2);

                promise2.resolve();
                queue.execute(); // ensure no hard failure when no tasks in queue
            });

            it('Executes task even when previous task failed', function () {
                promise1.reject();
                assert.equal(flag, "two");
                assert.equal(callCount, 2);
                promise2.resolve();
            });

            it('Clears tasks by name', function () {
                assert.equal(queue.queue.length, 1);
                queue.addTask('doSomethingElse', function () {}, []);
                assert.equal(queue.queue.length, 2);
                queue.clearTasks('updateFlag');
                assert.equal(queue.queue.length, 1);
                queue.clearTasks();
                assert.equal(queue.queue.length, 0);
            });
        });

        describe('WebFormSession', function () {
            var server,
                params,
                WebFormSession = webFormSession.WebFormSession;

            initialPageData.registerUrl(
                "report_formplayer_error",
                "/a/domain/cloudcare/apps/report_formplayer_error"
            );

            beforeEach(function () {
                // Setup HTML
                try {
                    affix('input#submit');
                    affix('#content');
                } catch (e) {
                    // temporarily catch this error while we work out issues running
                    // mocha tests with grunt-mocha. this passes fine in browser
                }

                // Setup Params object
                params = {
                    form_url: window.location.host,
                    onerror: sinon.spy(),
                    onload: sinon.spy(),
                    onsubmit: sinon.spy(),
                    onLoading: sinon.spy(),
                    onLoadingComplete: sinon.spy(),
                    resourceMap: sinon.spy(),
                    session_data: {},
                    xform_url: 'http://xform.url/',
                    action: 'dummy',
                };

                // Setup fake server
                server = sinon.fakeServer.create();
                server.respondWith(
                    'POST',
                    new RegExp(params.xform_url + '.*'),
                    [
                        200,
                        { 'Content-Type': 'application/json' },
                        '{ "status": "success", "session_id": "my-session" }',
                    ]
                );

                // Setup server constants
                window.XFORM_URL = 'dummy';

                // Setup stubs
                $.cookie = sinon.stub();
                sinon.stub(Utils, 'initialRender');
                sinon.stub(formUI, 'getIx').callsFake(function () { return 3; });
            });

            afterEach(function () {
                $('#submit').remove();
                try {
                    server.restore();
                } catch (e) {
                    // temporarily catch these errors while we work on issues with
                    // running mocha tests with grunt-mocha. this passes fine in
                    // the browser.
                }
                Utils.initialRender.restore();
                formUI.getIx.restore();
                $.unsubscribe();
            });

            it('Should queue requests', function () {
                var sess = WebFormSession(params);
                sess.serverRequest({}, sinon.spy(), false);

                sinon.spy(sess.taskQueue, 'execute');

                assert.isFalse(!!$('input#submit').prop('disabled'));
                assert.isFalse(sess.taskQueue.execute.calledOnce);
                server.respond();
                assert.isFalse(!!$('input#submit').prop('disabled'));
                assert.isTrue(sess.taskQueue.execute.calledOnce);
            });

            it('Should only subscribe once', function () {
                var spy = sinon.spy(),
                    spy2 = sinon.spy(),
                    sess = WebFormSession(params),
                    sess2 = WebFormSession(params);

                sinon.stub(sess, 'newRepeat').callsFake(spy);
                sinon.stub(sess2, 'newRepeat').callsFake(spy2);

                $.publish('formplayer.' + constants.NEW_REPEAT, {});
                assert.isFalse(spy.calledOnce);
                assert.isTrue(spy2.calledOnce);
            });

            it('Should block requests', function () {
                var sess = WebFormSession(params);

                // First blocking request
                $.publish('formplayer.' + constants.NEW_REPEAT, {});

                assert.equal(sess.blockingStatus, constants.BLOCK_ALL);

                // Attempt another request
                $.publish('formplayer.' + constants.NEW_REPEAT, {});

                server.respond();

                assert.equal(sess.blockingStatus, constants.BLOCK_NONE);
                // One call to new-repeat
                assert.equal(server.requests.length, 1);
            });

            it('Should not block requests', function () {
                var sess = WebFormSession(params);

                var question = {
                    answer: sinon.spy(),
                    form: function () {
                        return {
                            erroredLabels: function () {
                                return [];
                            },
                        };
                    },
                    entry: {
                        xformAction: constants.ANSWER,
                        xformParams: function () { return {}; },
                    },
                };

                // First blocking request
                $.publish('formplayer.' + constants.ANSWER, question);

                assert.equal(sess.blockingStatus, constants.BLOCK_SUBMIT);

                // Attempt another request
                $.publish('formplayer.' + constants.ANSWER, question);

                server.respond();

                assert.equal(sess.blockingStatus, constants.BLOCK_NONE);
                // two calls to answer
                assert.equal(server.requests.length, 2);

            });

            it('Should handle error in callback', function () {
                var sess = WebFormSession(params);

                sess.handleSuccess({}, 'action', sinon.stub().throws());

                assert.isTrue(sess.onerror.calledOnce);
            });

            it('Should handle error in response', function () {
                var sess = WebFormSession(params),
                    cb = sinon.stub();

                sess.handleSuccess({ status: 'error' }, 'action', cb);

                assert.isTrue(sess.onerror.calledOnce);
                assert.isFalse(cb.calledOnce);
            });

            it('Should handle failure in ajax call', function () {
                var sess = WebFormSession(params);
                sess.handleFailure({ responseJSON: { message: 'error' } });

                assert.isTrue(sess.onerror.calledOnce);
            });

            it('Should handle timeout error', function () {
                var sess = WebFormSession(params);
                sess.handleFailure({}, 'action', 'timeout');

                assert.isTrue(sess.onerror.calledOnce);
                assert.isTrue(sess.onerror.calledWith({
                    human_readable_message: errors.TIMEOUT_ERROR,
                    is_html: false,
                    reportToHq: false,
                }));
            });

            it('Should ensure session id is set', function () {
                var sess = WebFormSession(params);
                sess.loadForm($('div'), 'en');
                assert.equal(sess.session_id, null);

                server.respond();
                assert.equal(sess.session_id, 'my-session');
            });
        });

        describe('Question Validation', function () {
            let server,
                formJSON,
                WebFormSession = webFormSession.WebFormSession;

            initialPageData.registerUrl(
                "report_formplayer_error",
                "/a/domain/cloudcare/apps/report_formplayer_error"
            );

            beforeEach(function () {
                // Setup HTML
                try {
                    affix('input#submit');
                    affix('#content');
                } catch (e) {
                    // temporarily catch this error while we work out issues running
                    // mocha tests with grunt-mocha. this passes fine in browser
                }

                formJSON = {
                    form_url: window.location.host,
                    onerror: sinon.spy(),
                    onload: sinon.spy(),
                    onsubmit: sinon.spy(),
                    onLoading: sinon.spy(),
                    onLoadingComplete: sinon.spy(),
                    resourceMap: sinon.spy(),
                    session_data: {},
                    xform_url: 'http://xform.url/',
                    action: 'dummy',
                    tree: [Fixtures.textJSON({ix: "0"})],
                };

                // Setup fake server
                server = sinon.fakeServer.create();

                // Setup server constants
                window.XFORM_URL = 'dummy';

                // Setup stubs
                $.cookie = sinon.stub();
                sinon.stub(Utils, 'initialRender');
                this.clock = sinon.useFakeTimers();

                /**
                 * Helper function to make requests and mock responses. Also
                 * checks for errors.
                 * @param action: One of the xform actions listed in `constants`
                 * @param args: Arguments to publish with the action
                 * @param responseBody: The mock request response
                 */
                this.makeRequest = function (action, args, responseBody) {
                    $.publish('formplayer.' + action, args);
                    if (action === constants.SUBMIT) {
                        this.clock.tick(250);
                    }
                    if (typeof responseBody !== "string") {
                        responseBody = JSON.stringify(responseBody);
                    }
                    server.respond([200, { 'Content-Type': 'application/json' }, responseBody]);
                    assert.isTrue(formJSON.onerror.notCalled, "Error occurred handling request");
                };
            });

            afterEach(function () {
                $('#submit').remove();
                try {
                    server.restore();
                } catch (e) {
                    // temporarily catch these errors while we work on issues with
                    // running mocha tests with grunt-mocha. this passes fine in
                    // the browser.
                }
                Utils.initialRender.restore();
                $.unsubscribe();
                this.clock.restore();
            });

            it('Question validation updated after answer', function () {
                WebFormSession(formJSON);
                let form = formUI.Form(formJSON);

                this.makeRequest(constants.ANSWER, form.children()[0].children()[0], {
                    "status": "validation-error",
                    "type": "constraint",
                });
                assert.isFalse(form.children()[0].children()[0].isValid(), "Expected question to be invalid");
                assert.deepEqual(form.erroredLabels(), {});
            });

            it('Question validation updated on submit', function () {
                WebFormSession(formJSON);
                let form = formUI.Form(formJSON);

                this.makeRequest(constants.SUBMIT, form, {
                    "status": "validation-error",
                    "errors": {"0": {"status": "validation-error","type": "constraint"}},
                });
                assert.isFalse(form.children()[0].children()[0].isValid(), "Expected question to be invalid");
                assert.deepEqual(form.erroredLabels(), {});
            });

            it('Label validation updated on submit', function () {
                formJSON.tree.push(Fixtures.labelJSON({ix: "1"}));
                WebFormSession(formJSON);
                let form = formUI.Form(formJSON);

                this.makeRequest(constants.SUBMIT, form, {
                    "status": "validation-error",
                    "errors": {"1": {"status": "validation-error","type": "constraint"}},
                });
                assert.isFalse(form.children()[1].children()[0].isValid(), "Expected question to be invalid");
                assert.deepEqual(form.erroredLabels(), {"1": "OK"});
            });

            it('Label validation cleared on answer', function () {
                formJSON.tree.push(Fixtures.labelJSON({ix: "1"}));
                WebFormSession(formJSON);
                let form = formUI.Form(formJSON);

                this.makeRequest(constants.SUBMIT, form, {
                    "status": "validation-error",
                    "errors": {"1": {"status": "validation-error","type": "constraint"}},
                });
                assert.isFalse(form.children()[1].children()[0].isValid(), "Expected question to be invalid");
                assert.deepEqual(form.erroredLabels(), {"1": "OK"});

                this.makeRequest(constants.ANSWER, form.children()[0].children()[0], {
                    "status": "accepted",
                    "errors": {},
                    "tree": [
                        Fixtures.textJSON({ix: "0", answer: "a"}),
                        Fixtures.labelJSON({ix: "1", answer: "OK"}),
                    ],
                });

                // assert.isTrue(form.children()[1].children()[0].isValid(), "Expected question to be invalid");
                // assert.deepEqual(form.erroredLabels(), {});

            });

            it('Label validation handle missing label', function () {
                formJSON.tree.push(Fixtures.labelJSON({ix: "1"}));
                WebFormSession(formJSON);
                let form = formUI.Form(formJSON);

                this.makeRequest(constants.SUBMIT, form, {
                    "status": "validation-error",
                    "errors": {"1": {"status": "validation-error","type": "constraint"}},
                });
                assert.isFalse(form.children()[1].children()[0].isValid(), "Expected question to be invalid");
                assert.deepEqual(form.erroredLabels(), {"1": "OK"});

                this.makeRequest(constants.ANSWER, form.children()[0].children()[0], {
                    "status": "accepted",
                    "errors": {},
                    "tree": [
                        Fixtures.textJSON({ix: "0", answer: "a"}),
                        // label no longer visible so removed from the tree
                    ],
                });

                assert.deepEqual(form.erroredLabels(), {});
            });
        });
    });
});
