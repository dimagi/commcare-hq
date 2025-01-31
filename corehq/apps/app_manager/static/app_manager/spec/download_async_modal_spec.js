/* eslint-env mocha */

import $ from "jquery";
import sinon from "sinon/pkg/sinon";

import asyncDownloader from "app_manager/js/download_async_modal";

describe('Async Download Modal', function () {
    var url = 'test_url';

    describe('#AsyncDownloader.isDone', function () {
        var downloader = null,
            modal = $('#modal'),
            downloadPollId = '12345';

        beforeEach(function () {
            downloader = asyncDownloader.asyncDownloader(modal);
            downloader.download_poll_id = downloadPollId;
        });

        var testDone = [
            {
                input: 'progress ready_' + downloadPollId,
                expected: true,
            }, {
                input: 'ready_' + downloadPollId,
                expected: true,
            }, {
                input: 'progress error_' + downloadPollId,
                expected: true,
            },
        ];

        testDone.forEach(function (test) {
            it('should be done for input "' + test.input + '"', function () {
                assert.ok(downloader.isDone(test.input));
            });
        });

        var testNotDone = [
            {
                input: null,
                expected: false,
            }, {
                input: undefined,
                expected: false,
            }, {
                input: '',
                expected: false,
            }, {
                input: 'progress',
                expected: false,
            },
        ];

        testNotDone.forEach(function (test) {
            it('should not be done for input "' + test.input + '"', function () {
                assert.notOk(downloader.isDone(test.input));
            });
        });
    });

    describe('#AsyncDownloader', function () {
        var downloader = null,
            modal = $('#download-zip-modal-test'),
            ajaxStub,
            clock;

        before(function () {
            clock = sinon.useFakeTimers();
            downloader = asyncDownloader.asyncDownloader(modal);
        });

        after(function () {
            clock.restore();
        });

        beforeEach(function () {
            ajaxStub = sinon.stub($, 'ajax');
            downloader.init();
        });

        afterEach(function () {
            ajaxStub.restore();
        });

        it('should only make one download request', function (done) {
            downloader.generateDownload(url);
            assert.equal($.ajax.callCount, 1, 'Only expecting 1 ajax call');
            done();
        });

        function verifyDownload(state) {
            var pollUrl = 'ajax/temp/123',
                downloadId = '123';
            ajaxStub.reset();
            ajaxStub.onFirstCall(0).yieldsTo("success", {
                download_id: downloadId,
                download_url: pollUrl,
            });
            ajaxStub.onSecondCall().yieldsTo("success", 'html progress content');
            ajaxStub.onThirdCall().yieldsTo("success", 'html read content ' + state + downloadId);
            downloader.generateDownload(url);

            assert.equal($.ajax.callCount, 2);
            assert.equal(ajaxStub.firstCall.args[0].url, url);
            assert.equal(ajaxStub.secondCall.args[0].url, pollUrl);

            clock.tick(downloader.POLL_FREQUENCY);
            assert.equal($.ajax.callCount, 3);
            assert.equal(ajaxStub.thirdCall.args[0].url, pollUrl);
        }

        var testsState = [{
            state: 'ready_',
        }, {
            state: 'error_',
        }];

        testsState.forEach(function (test) {
            it('should poll until ' + test.state, function () {
                verifyDownload(test.state);
            });
        });

        it('should handle multiple downloads correctly', function () {
            verifyDownload('ready_');
            verifyDownload('ready_');
        });
    });
});
