hqDefine("hqwebapp/spec/main", [
    "analytix/js/google",
    "analytix/js/kissmetrix",
    "mocha/mocha",
    "chai/chai",
    "sinon/pkg/sinon",
], function (
    googleAnalytics,
    kissAnalytics,
    mocha,
    chai,
    sinon
) {
    // TODO: DRY up with mocha/base.html
    mocha.setup('bdd')
    window.assert = chai.assert

    function gettext(str) {
        return str;
    }
    window.gettext = gettext;

    googleAnalytics.track.event = sinon.spy();
    googleAnalytics.track.click = sinon.spy();
    kissAnalytics.track.event = sinon.spy();

    hqRequire([
        "hqwebapp/spec/assert_properties_spec",
        "hqwebapp/spec/inactivity_spec",
    ], function () {
        // TODO: DRY up with mocha/base.html
        if (navigator.userAgent.indexOf('PhantomJS') < 0) {
            mocha.run();
        }
    });

    return 1;
});
