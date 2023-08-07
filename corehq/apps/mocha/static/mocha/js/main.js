hqDefine("mocha/js/main", [
    "mocha/mocha",
    "chai/chai",
    "sinon/pkg/sinon",
    "analytix/js/google",
    "analytix/js/kissmetrix",
], function (
    mocha,
    chai,
    sinon,
    googleAnalytics,
    kissAnalytics
) {
    mocha.setup('bdd');
    window.assert = chai.assert;

    function gettext(str) {
        return str;
    }
    window.gettext = gettext;

    googleAnalytics.track.event = sinon.spy();
    googleAnalytics.track.click = sinon.spy();
    kissAnalytics.track.event = sinon.spy();

    var run = function () {
        if (navigator.userAgent.indexOf('PhantomJS') < 0) {
            mocha.run();
        }
    };

    return {
        run: run,
    };
});
