/* eslint-env mocha */

describe('AppDiff', function() {
    var AppDiff = hqImport('app_manager/js/releases/app_diff');

    describe('HtmlUtils', function() {
        var HtmlUtils = AppDiff.HtmlUtils;

        describe('#makeOl', function() {

            it('should make an OL with icon', function() {
                var el = HtmlUtils.makeOl('myclass', 'file');
                assert.equal(
                    el,
                    '<ol class="myclass"><i class="fa fa-file"></i>&nbsp;<span class="###"></span>'
                );
            });

            it('should make an OL without icon', function() {
                var el = HtmlUtils.makeOl('myclass');
                assert.equal(el, '<ol class="myclass"><span class="###"></span>');
            });

            it('should close an OL', function() {
                var el = HtmlUtils.closeOl();
                assert.equal(el, '</ol>');
            });
        });

        describe('#makeLi', function() {

            it('should make an Li with icon', function() {
                var el = HtmlUtils.makeLi('hi', 'cls', 'file');
                assert.equal(
                    el,
                    '<li class="cls"><i class="fa fa-file"></i>&nbsp;<span class="###">hi</span>'
                );
            });

            it('should make an Li and close it', function() {
                var el = HtmlUtils.makeLi('hi', 'cls', 'file', true);
                assert.equal(
                    el,
                    '<li class="cls"><i class="fa fa-file"></i>&nbsp;<span class="###">hi</span></li>'
                );
            });

        });

        describe('#makeSpan', function() {
            it('should make an Li with icon', function() {
                var el = HtmlUtils.makeSpan('hi', 'cls', 'file');
                assert.equal(
                    el,
                    '<span class="cls"><i class="fa fa-file"></i>&nbsp;<span class="###">hi</span></span>'
                );
            });
        });
    });

    describe('ModuleDatum', function() {
        var ModuleDatum = AppDiff.ModuleDatum;
        var datum = {
            name: { 'en': 'Module' },
            shortComment: 'Hello',
            forms: [
                {
                    name: { 'en': 'Form' },
                    shortComment: 'Hi',
                    questions: [
                        {
                            comment: 'Hi',
                            hashtagValue: '#form/name',
                            label: 'What is your name',
                            calculate: '1 = 1',
                            relevant: '1 = 1',
                        },
                    ],
                },
            ],
        };
        var checkHTML = function(html) {
            var doc = document.createElement('div');
            doc.innerHTML = html;
            return (doc.innerHTML === html);
        };

        it('should generate a toString', function() {
            var html = (new ModuleDatum(datum, { lang: 'en' })).toString();
            assert.isTrue(checkHTML(html));
        });

    });
});
