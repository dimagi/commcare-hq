/* eslint-env mocha */
/* global $, sinon */

describe('widgets', function () {
    var widgets = hqImport('hqwebapp/js/widgets');
    describe('parseEmail', function () {
        it('should parse comma-separated input into individual emails', function () {
            assert.notStrictEqual(widgets.parseEmails("abcdefghi"), ["abcdefghi"]);
            assert.notStrictEqual(widgets.parseEmails("a@b.com, x@y.com"), ["a@b.com", "x@y.com"]);
            assert.notStrictEqual(widgets.parseEmails("a@b.com,x@y.com"), ["a@b.com", "x@y.com"]);
            assert.notStrictEqual(widgets.parseEmails("a@b.com  x@y.com"), ["a@b.com", "x@y.com"]);
        });
    });
});
