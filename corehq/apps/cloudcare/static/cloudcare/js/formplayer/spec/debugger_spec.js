'use strict';
/* eslint-env mocha */
hqDefine("cloudcare/js/formplayer/spec/debugger_spec", function () {
    describe('Debugger', function () {
        let EvaluateXPath = hqImport('cloudcare/js/debugger/debugger').EvaluateXPath,
            API = hqImport('cloudcare/js/debugger/debugger').API,
            CloudCareDebugger = hqImport('cloudcare/js/debugger/debugger').CloudCareDebuggerFormEntry;

        describe('EvaluateXPath', function () {
            it('should correctly match xpath input', function () {
                let evalXPath = new EvaluateXPath(),
                    result;

                result = evalXPath.matcher('', '');
                assert.equal(result, null);

                // Should match /
                result = evalXPath.matcher('', '/data');
                assert.equal(result, '/data');

                // Should not match parens
                result = evalXPath.matcher('', 'concat(');
                assert.equal(result, null);

                // Should not match queries less than 1
                result = evalXPath.matcher('', 'c');
                assert.equal(result, null);

                // Should match queries greater than 1
                result = evalXPath.matcher('', 'co');
                assert.equal(result, 'co');
            });
        });

        describe('Update logic', function () {
            let ccDebugger;

            beforeEach(function () {
                ccDebugger = new CloudCareDebugger();
                sinon.stub(API, 'evaluateXPath').returns($.Deferred());
                sinon.stub(API, 'formattedQuestions').returns($.Deferred());
            });

            afterEach(function () {
                API.evaluateXPath.restore();
                API.formattedQuestions.restore();
            });

            it('Should update when opened', function () {
                assert.isTrue(ccDebugger.isMinimized());

                ccDebugger.toggleState();
                assert.isFalse(ccDebugger.isMinimized());
                assert.isTrue(API.formattedQuestions.calledOnce);

                ccDebugger.toggleState();
                assert.isTrue(ccDebugger.isMinimized());
                assert.isTrue(API.formattedQuestions.calledOnce);
            });

        });

        describe('Format Result', function () {
            let evalXPath = new EvaluateXPath();
            it('Should handle single values correctly', function () {
                assert.equal(
                    evalXPath.formatResult("<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<result>fun</result>\n"),
                    'fun'
                );
            });
            it('Should handle the empty string value correctly', function () {
                assert.equal(
                    evalXPath.formatResult("<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<result/>\n"),
                    ''
                );
            });
            it('Should handle nested xml correctly', function () {
                assert.equal(
                    evalXPath.formatResult("<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<result>\n  <session>\n    <data/>\n    <context>\n      <deviceid>Formplayer</deviceid>\n      <appversion>Formplayer Version: 2.36</appversion>\n      <username>droberts@dimagi.com</username>\n      <userid>9393007a6921eecd4a9f20eefb5c7a8e</userid>\n    </context>\n    <user>\n      <data>\n        <commcare_first_name/>\n        <commcare_phone_number/>\n        <commcare_last_name/>\n        <commcare_project>openmrs-test</commcare_project>\n        <user_type>standard</user_type>\n      </data>\n    </user>\n  </session>\n</result>\n"),
                    '  <session>\n    <data/>\n    <context>\n      <deviceid>Formplayer</deviceid>\n      <appversion>Formplayer Version: 2.36</appversion>\n      <username>droberts@dimagi.com</username>\n      <userid>9393007a6921eecd4a9f20eefb5c7a8e</userid>\n    </context>\n    <user>\n      <data>\n        <commcare_first_name/>\n        <commcare_phone_number/>\n        <commcare_last_name/>\n        <commcare_project>openmrs-test</commcare_project>\n        <user_type>standard</user_type>\n      </data>\n    </user>\n  </session>'
                );
            });
        });
    });
});
