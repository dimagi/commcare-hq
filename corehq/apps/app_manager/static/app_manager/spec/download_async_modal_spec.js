/* global chai, $, sinon */

describe('Async Download Modal', function() {
    var downloader = null,
        expect = chai.expect,
        url = 'test_url';

    describe('#AsyncDownloader.isDone', function() {
        var modal = $('#modal'),
            download_poll_id = '12345';

        beforeEach(function() {
            downloader = new AsyncDownloader(modal, url);
            downloader.download_poll_id = download_poll_id;
        });

        afterEach(function() {
            downloader.init();
        });

        var test_done = [
            {input: null, expected: false},
            {input: undefined, expected: false},
            {input: '', expected: false},
            {input: 'progress', expected: false},
            {input: 'progress ready_' + download_poll_id, expected: true},
            {input: 'progress error_' + download_poll_id, expected: true}

        ];

        test_done.forEach(function(test) {
            it('should return ' + test.expected + ' for input "' + test.input + '"', function() {
                expect(downloader.isDone(test.input)).to.be.equal(test.expected);
            });
        });

        it('should return false for empty input', function() {
            expect(downloader.isDone('')).to.be.false;
        });
    });

    describe('#AsyncDownloader', function() {
        var modal = $('#download-zip-modal-test'),
            ajax_stub;

        beforeEach(function() {
            ajax_stub = sinon.stub($, 'ajax');
            downloader = new AsyncDownloader(modal, url);
            downloader.POLL_FREQUENCY = 0;
        });

        afterEach(function() {
          ajax_stub.restore();
        });

        it('should only make one download request', function(done) {
            modal.modal({show: true});
            expect($.ajax.callCount).to.equal(1, 'Only expecting 1 ajax call');
            done();
        });

        var tests_state = [
            {state: 'ready_'},
            {state: 'error_'}
        ];

        tests_state.forEach(function(test) {
            it('should poll until ' + test.state, function(done) {
                var pollUrl = 'ajax/temp/123',
                    downloadId = '123';
                ajax_stub.onFirstCall(0).yieldsTo("success", {
                    download_id: downloadId,
                    download_url: pollUrl
                });
                ajax_stub.onSecondCall().yieldsTo("success", 'html progress content');
                ajax_stub.onThirdCall().yieldsTo("success", 'html read content ' + test.state + downloadId);
                modal.modal({show: true});
                setTimeout(function () {
                    expect($.ajax.callCount).to.equal(3, 'Expecting 3 ajax calls');
                    expect(ajax_stub.firstCall.args[0].url).to.equal(url);
                    expect(ajax_stub.secondCall.args[0].url).to.equal(pollUrl);
                    expect(ajax_stub.thirdCall.args[0].url).to.equal(pollUrl);
                    done();
                }, 5);
            });
        });
    });
});
