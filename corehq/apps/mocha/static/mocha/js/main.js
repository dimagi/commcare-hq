import mocha from "mocha/mocha";
import chai from "chai/chai";
import sinon from "sinon";
import googleAnalytics from "analytix/js/google";
import kissAnalytics from "analytix/js/kissmetrix";

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

export default {
    run: run,
};
