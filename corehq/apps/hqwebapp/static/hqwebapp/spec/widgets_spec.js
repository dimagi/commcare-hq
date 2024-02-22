/* eslint-env mocha */
hqDefine("hqwebapp/spec/widgets_spec", [
    'hqwebapp/js/bootstrap3/widgets',
], function (
    widgets
) {
    describe('widgets', function () {
        describe('parseEmail', function () {
            it('should parse comma-separated input into individual emails', function () {
                assert.deepEqual(widgets.parseEmails("abcdefghi"), ["abcdefghi"]);
                assert.deepEqual(widgets.parseEmails("a@b.com, x@y.com"), ["a@b.com", "x@y.com"]);
                assert.deepEqual(widgets.parseEmails("a@b.com,x@y.com"), ["a@b.com", "x@y.com"]);
                assert.deepEqual(widgets.parseEmails("a@b.com  x@y.com"), ["a@b.com", "x@y.com"]);
            });
        });
    });
});
