describe('WebForm', function() {

    describe('TaskQueue', function() {
        var tq,
            taskOne,
            taskTwo;
        beforeEach(function() {
            tq = new TaskQueue();
            taskOne = sinon.spy();
            taskTwo = sinon.spy();
            tq.addTask('one', taskOne, [1,2,3])
            tq.addTask('two', taskTwo, [5,6,7])
        });

        it('Executes tasks in order', function() {
            tq.execute()
            expect(taskOne.calledOnce).toBe(true);
            expect(taskOne.calledWith(1, 2, 3)).toBe(true);
            expect(taskTwo.calledOnce).toBe(false);

            tq.execute()
            expect(taskTwo.calledOnce).toBe(true);
            expect(taskTwo.calledWith(5, 6, 7)).toBe(true);
            expect(tq.queue.length).toBe(0);

            tq.execute() // ensure no hard failure when no tasks in queue
        })

        it('Executes tasks by name', function() {
            tq.execute('two');
            expect(taskOne.calledOnce).toBe(false);
            expect(taskTwo.calledOnce).toBe(true);
            expect(tq.queue.length).toBe(1);

            tq.execute('cannot find me');
            expect(tq.queue.length).toBe(1);

            tq.execute()
            tq.execute()
        });

        it('Clears tasks by name', function() {
            tq.addTask('two', taskTwo, [5,6,7]);
            expect(tq.queue.length).toBe(3);

            tq.clearTasks('two');
            expect(tq.queue.length).toBe(1);

            tq.clearTasks();
            expect(tq.queue.length).toBe(0);
        });
    });

    describe('WebFormSession', function() {
        var server,
            params;

        beforeEach(function() {
            // Setup HTML
            affix('input#submit');
            affix('#content');

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
                xform_url: 'http://xform.url/'
            };

            // Setup fake server
            server = sinon.fakeServer.create();
            server.respondWith(
                params.xform_url,
                [200,
                { 'Content-Type': 'application/json' },
                '{ "status": "success", "session_id": "my-session" }']);

            // Setup server constants
            window.XFORM_URL = 'dummy';

            // Setup stubs
            $.cookie = sinon.stub();
            sinon.stub(Formplayer.Utils, 'initialRender');
            sinon.stub(window, 'getIx', function() { return 3; });
        });

        afterEach(function() {
            $('#submit').remove();
            server.restore();
            Formplayer.Utils.initialRender.restore();
            getIx.restore();
            $.unsubscribe();
        });

        it('Should queue requests', function() {
            var sess = new WebFormSession(params);
            sess.serverRequest({}, sinon.spy(), false);

            sinon.spy(sess.taskQueue, 'execute');

            expect(!!$('input#submit').attr('disabled')).toBe(false);
            expect(sess.taskQueue.execute.calledOnce).toBe(false);
            server.respond();
            expect(!!$('input#submit').attr('disabled')).toBe(false);
            expect(sess.taskQueue.execute.calledOnce).toBe(true);
        });

        it('Should only subscribe once', function() {
            var spy = sinon.spy(),
                spy2 = sinon.spy(),
                sess = new WebFormSession(params),
                sess2 = new WebFormSession(params);

            sinon.stub(sess, 'newRepeat', spy);
            sinon.stub(sess2, 'newRepeat', spy2);

            $.publish('formplayer.' + Formplayer.Const.NEW_REPEAT, {});
            expect(spy.calledOnce).toBe(false);
            expect(spy2.calledOnce).toBe(true);
        });

        it('Should block requests', function() {
            var sess = new WebFormSession(params);

            // First blocking request
            $.publish('formplayer.' + Formplayer.Const.NEW_REPEAT, {});

            expect(sess.blockingRequestInProgress).toBe(true);

            // Attempt another request
            $.publish('formplayer.' + Formplayer.Const.NEW_REPEAT, {});

            server.respond();

            expect(sess.blockingRequestInProgress).toBe(false);
            // One call to new-repeat
            expect(server.requests.length).toEqual(1);
        });

        it('Should not block requests', function() {
            var sess = new WebFormSession(params);

            // First blocking request
            $.publish('formplayer.' + Formplayer.Const.ANSWER, { answer: sinon.spy() });

            expect(sess.blockingRequestInProgress).toBeFalsy(false);

            // Attempt another request
            $.publish('formplayer.' + Formplayer.Const.ANSWER, { answer: sinon.spy() });

            server.respond();

            expect(sess.blockingRequestInProgress).toBe(false);
            // two calls to answer
            expect(server.requests.length).toEqual(2);

        });

        it('Should handle error in callback', function() {
            var sess = new WebFormSession(params);

            sess.handleSuccess({}, sinon.stub().throws());

            expect(sess.onerror.calledOnce).toBe(true);
        });

        it('Should handle error in response', function() {
            var sess = new WebFormSession(params),
                cb = sinon.stub();

            sess.handleSuccess({ status: 'error' }, cb);

            expect(sess.onerror.calledOnce).toBe(true);
            expect(cb.calledOnce).toBe(false);
        });

        it('Should handle failure in ajax call', function() {
            var sess = new WebFormSession(params);
            sess.handleFailure({ responseJSON: { message: 'error' } });

            expect(sess.onerror.calledOnce).toBe(true);
        });

        it('Should handle timeout error', function() {
            var sess = new WebFormSession(params);
            sess.handleFailure({}, 'timeout');

            expect(sess.onerror.calledOnce).toBe(true);
            expect(sess.onerror.calledWith({
                human_readable_message: Formplayer.Errors.TIMEOUT_ERROR
            })).toBe(true);
        });

        it('Should ensure session id is set', function() {
            var sess = new WebFormSession(params),
                spy = sinon.spy(WebFormSession.prototype, 'renderFormXml');
            sess.loadForm($('div'), 'en');
            expect(sess.session_id).toBe(null);

            server.respond();
            expect(sess.session_id).toBe('my-session');
            WebFormSession.prototype.renderFormXml.restore();
        });
    });
});
