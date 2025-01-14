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
console.log("\n\nuserAgent: " + navigator.userAgent + "\n\n");
        if (navigator.userAgent.indexOf('PhantomJS') < 0) {
console.log("so i am RUNNING");
            mocha.run();
        } else {
console.log("so i do nothing");
        }
    };

    return {
        run: run,
    };
});
