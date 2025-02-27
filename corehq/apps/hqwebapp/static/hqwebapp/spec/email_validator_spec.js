/* eslint-env mocha */
hqDefine("hqwebapp/spec/email_validator_spec", [
    'hqwebapp/js/constants',
], function (
    constants,
) {
    describe('email_validator', function () {
        const re = constants.EMAIL_VALIDATION_REGEX;
        const testEmail = email => re.test(email);

        it('should allow simple email addresses', function () {
            assert.ok(testEmail('simple@example.com'));
        });

        it('should allow capital letters in the local part', function () {
            assert.ok(testEmail('Capital@example.com'));
            assert.ok(testEmail('VERYCAPITAL@example.com'));
        });

        it('should allow capital letters in the domain part', function () {
            assert.ok(testEmail('email@Example.com'));
            assert.ok(testEmail('email@EXAMPLE.COM'));
        });

        it('should allow digits in the local part', function () {
            assert.ok(testEmail('email123@example.com'));
        });

        it('should allow specified special characters in the local part', function () {
            assert.ok(testEmail('.\x01!#$%&"\'*+/=?^_`{|}~-@example.com'));
        });

        it('should allow subdomains', function () {
            assert.ok(testEmail('email@subdomain.example.com'));
        });

        it('should allow hyphens in domain names', function () {
            assert.ok(testEmail('email@ex-ample.com'));
        });

        it('should allow IP addresses in brackets as the domain', function () {
            assert.ok(testEmail('whosaidthiswasok@[127.0.0.1]'));
        });

        it('should reject missing @ symbol', function () {
            assert.notOk(testEmail('notanemail'));
        });

        it('should reject missing local part', function () {
            assert.notOk(testEmail('@example.com'));
        });

        it('should reject missing top-level domain', function () {
            assert.notOk(testEmail('nothing@toseehere'));
            assert.notOk(testEmail('noteven@toseehere.'));
        });

        it('should reject invalid characters in the domain part', function () {
            const emails = [
                // allowed in local part but not domain
                'me@ex\x01ample.com',
                'me@ex!ample.com',
                'me@ex#ample.com',
                'me@ex$ample.com',
                'me@ex%ample.com',
                'me@ex&ample.com',
                'me@ex"ample.com',
                'me@ex\'ample.com',
                'me@ex*ample.com',
                'me@ex+ample.com',
                'me@ex/ample.com',
                'me@ex=ample.com',
                'me@ex?ample.com',
                'me@ex^ample.com',
                'me@ex_ample.com',
                'me@ex`ample.com',
                'me@ex{ample}.com',
                'me@ex|ample.com',
            ];
            emails.forEach(email => assert.notOk(testEmail(email)));
        });
    });
});
