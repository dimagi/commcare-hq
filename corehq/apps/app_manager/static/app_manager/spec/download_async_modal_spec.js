/* global chai, $, sinon */

describe('Async Download Modal', function() {
    var url = 'test_url';
    var AsyncDownloader = hqImport('app_manager/js/download_async_modal').AsyncDownloader;

    describe('#AsyncDownloader.isDone', function() {
        var downloader = null,
            modal = $('#modal'),
            download_poll_id = '12345';

        beforeEach(function() {
            downloader = new AsyncDownloader(modal);
            downloader.download_poll_id = download_poll_id;
        });

        var test_done = [
            {
                input: 'progress ready_' + download_poll_id,
                expected: true
            }, {
                input: 'ready_' + download_poll_id,
                expected: true
            }, {
                input: 'progress error_' + download_poll_id,
                expected: true
            }
        ];

        test_done.forEach(function(test) {
            it('should be done for input "' + test.input + '"', function() {
                assert.ok(downloader.isDone(test.input));
            });
        });

        var test_not_done = [
            {
                input: null,
                expected: false
            }, {
                input: undefined,
                expected: false
            }, {
                input: '',
                expected: false
            }, {
                input: 'progress',
                expected: false
            }
        ];

        test_not_done.forEach(function(test) {
            it('should not be done for input "' + test.input + '"', function() {
                assert.notOk(downloader.isDone(test.input));
            });
        });
    });

    describe('#AsyncDownloader', function() {
        var downloader = null,
            modal = $('#download-zip-modal-test'),
            ajax_stub,
            clock;

        before(function() {
            clock = sinon.useFakeTimers();
            downloader = new AsyncDownloader(modal);
        });

        after(function() {
            clock.restore();
        });

        beforeEach(function() {
            ajax_stub = sinon.stub($, 'ajax');
            downloader.init();
        });

        afterEach(function() {
            ajax_stub.restore();
        });

        it('should only make one download request', function(done) {
            downloader.generateDownload(url);
            assert.equal($.ajax.callCount, 1, 'Only expecting 1 ajax call');
            done();
        });

        function verify_download(state) {
            var pollUrl = 'ajax/temp/123',
                downloadId = '123';
            ajax_stub.reset();
            ajax_stub.onFirstCall(0).yieldsTo("success", {
                download_id: downloadId,
                download_url: pollUrl
            });
            ajax_stub.onSecondCall().yieldsTo("success", 'html progress content');
            ajax_stub.onThirdCall().yieldsTo("success", 'html read content ' + state + downloadId);
            downloader.generateDownload(url);

            assert.equal($.ajax.callCount, 2);
            assert.equal(ajax_stub.firstCall.args[0].url, url);
            assert.equal(ajax_stub.secondCall.args[0].url, pollUrl);

            clock.tick(downloader.POLL_FREQUENCY);
            assert.equal($.ajax.callCount, 3);
            assert.equal(ajax_stub.thirdCall.args[0].url, pollUrl);
        }

        var tests_state = [{
            state: 'ready_'
        }, {
            state: 'error_'
        }];

        tests_state.forEach(function(test) {
            it('should poll until ' + test.state, function() {
                verify_download(test.state);
            });
        });

        it('should handle multiple downloads correctly', function() {
            verify_download('ready_');
            verify_download('ready_');
        });
    });
});
