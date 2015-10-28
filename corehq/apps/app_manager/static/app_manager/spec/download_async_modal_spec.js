/* global chai, $, sinon */

describe('Async Download Modal', function() {
    var downloader = null,
        expect = chai.expect,
        modal = $('#download-zip-modal-test'),
        url = 'test_url',
        ajax_stub;

    describe('#AsyncDownloader', function() {
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
