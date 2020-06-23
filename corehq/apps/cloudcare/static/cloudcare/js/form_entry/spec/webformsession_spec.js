/* globals Formplayer, TaskQueue, WebFormSession */
/* eslint-env mocha */

describe('WebForm', function () {

    describe('TaskQueue', function () {
        var tq,
            taskOne,
            taskTwo;
        beforeEach(function () {
            tq = new TaskQueue();
            taskOne = sinon.spy();
            taskTwo = sinon.spy();
            tq.addTask('one', taskOne, [1,2,3]);
            tq.addTask('two', taskTwo, [5,6,7]);
        });

        it('Executes tasks in order', function () {
            tq.execute();
            assert.isTrue(taskOne.calledOnce);
            assert.isTrue(taskOne.calledWith(1, 2, 3));
            assert.isFalse(taskTwo.calledOnce);

            tq.execute();
            assert.isTrue(taskTwo.calledOnce);
            assert.isTrue(taskTwo.calledWith(5, 6, 7));
            assert.equal(tq.queue.length, 0);

            tq.execute(); // ensure no hard failure when no tasks in queue
        });

        it('Executes tasks by name', function () {
            tq.execute('two');
            assert.isFalse(taskOne.calledOnce);
            assert.isTrue(taskTwo.calledOnce);
            assert.equal(tq.queue.length, 1);

            tq.execute('cannot find me');
            assert.equal(tq.queue.length, 1);

            tq.execute();
            tq.execute();
        });

        it('Clears tasks by name', function () {
            tq.addTask('two', taskTwo, [5,6,7]);
            assert.equal(tq.queue.length, 3);

            tq.clearTasks('two');
            assert.equal(tq.queue.length, 1);

            tq.clearTasks();
            assert.equal(tq.queue.length, 0);
        });
    });

    describe('WebFormSession', function () {
        var server,
            params;

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
            sinon.stub(Formplayer.Utils, 'initialRender');
            sinon.stub(window, 'getIx').callsFake(function () { return 3; });
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
            Formplayer.Utils.initialRender.restore();
            getIx.restore();
            $.unsubscribe();
        });

        it('Should queue requests', function () {
            var sess = new WebFormSession(params);
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
                sess = new WebFormSession(params),
                sess2 = new WebFormSession(params);

            sinon.stub(sess, 'newRepeat').callsFake(spy);
            sinon.stub(sess2, 'newRepeat').callsFake(spy2);

            $.publish('formplayer.' + Formplayer.Const.NEW_REPEAT, {});
            assert.isFalse(spy.calledOnce);
            assert.isTrue(spy2.calledOnce);
        });

        it('Should block requests', function () {
            var sess = new WebFormSession(params);

            // First blocking request
            $.publish('formplayer.' + Formplayer.Const.NEW_REPEAT, {});

            assert.equal(sess.blockingStatus, Formplayer.Const.BLOCK_ALL);

            // Attempt another request
            $.publish('formplayer.' + Formplayer.Const.NEW_REPEAT, {});

            server.respond();

            assert.equal(sess.blockingStatus, Formplayer.Const.BLOCK_NONE);
            // One call to new-repeat
            assert.equal(server.requests.length, 1);
        });

        it('Should not block requests', function () {
            var sess = new WebFormSession(params);

            // First blocking request
            $.publish('formplayer.' + Formplayer.Const.ANSWER, { answer: sinon.spy() });

            assert.equal(sess.blockingStatus, Formplayer.Const.BLOCK_SUBMIT);

            // Attempt another request
            $.publish('formplayer.' + Formplayer.Const.ANSWER, { answer: sinon.spy() });

            server.respond();

            assert.equal(sess.blockingStatus, Formplayer.Const.BLOCK_NONE);
            // two calls to answer
            assert.equal(server.requests.length, 2);

        });

        it('Should handle error in callback', function () {
            var sess = new WebFormSession(params);

            sess.handleSuccess({}, 'action', sinon.stub().throws());

            assert.isTrue(sess.onerror.calledOnce);
        });

        it('Should handle error in response', function () {
            var sess = new WebFormSession(params),
                cb = sinon.stub();

            sess.handleSuccess({ status: 'error' }, 'action', cb);

            assert.isTrue(sess.onerror.calledOnce);
            assert.isFalse(cb.calledOnce);
        });

        it('Should handle failure in ajax call', function () {
            var sess = new WebFormSession(params);
            sess.handleFailure({ responseJSON: { message: 'error' } });

            assert.isTrue(sess.onerror.calledOnce);
        });

        it('Should handle timeout error', function () {
            var sess = new WebFormSession(params);
            sess.handleFailure({}, 'action', 'timeout');

            assert.isTrue(sess.onerror.calledOnce);
            assert.isTrue(sess.onerror.calledWith({
                human_readable_message: Formplayer.Errors.TIMEOUT_ERROR,
                is_html: false,
            }));
        });

        it('Should ensure session id is set', function () {
            var sess = new WebFormSession(params),
                spy = sinon.spy(WebFormSession.prototype, 'renderFormXml');
            sess.loadForm($('div'), 'en');
            assert.equal(sess.session_id, null);

            server.respond();
            assert.equal(sess.session_id, 'my-session');
            WebFormSession.prototype.renderFormXml.restore();
        });
    });
});
