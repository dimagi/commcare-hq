/* eslint-env mocha */

describe('Util', function () {
    var API = hqImport("cloudcare/js/formplayer/menus/api"),
        FormplayerFrontend = hqImport("cloudcare/js/formplayer/app"),
        Util = hqImport("cloudcare/js/formplayer/utils/util");

    describe('#displayOptions', function () {
        beforeEach(function () {
            sinon.stub(Util, 'getDisplayOptionsKey').callsFake(function () { return 'mykey'; });
            window.localStorage.clear();
        });

        afterEach(function () {
            Util.getDisplayOptionsKey.restore();
        });

        it('should retrieve saved display options', function () {
            var options = { option: 'yes' };
            Util.saveDisplayOptions(options);
            assert.deepEqual(Util.getSavedDisplayOptions(), options);
        });

        it('should not fail on bad json saved', function () {
            localStorage.setItem(Util.getDisplayOptionsKey(), 'bad json');
            assert.deepEqual(Util.getSavedDisplayOptions(), {});
        });

    });

    describe('CloudcareUrl', function () {
        var stubs = {};

        /**
         *  The following tests all presume an app with this structure:
         *      m0: a menu that does not use cases
         *          m0-f0
         *      m1: a menu that uses cases
         *          m1-f0: a form that updates a case
         *  No menus use display-only forms.
         */

        beforeEach(function () {
            var currentUrl = new Util.CloudcareUrl({appId: 'abc123'});

            sinon.stub(Util, 'currentUrlToObject').callsFake(function () {
                return currentUrl;
            });
            sinon.stub(Util, 'setUrlToObject').callsFake(function (urlObject) {
                currentUrl = urlObject;
            });

            sinon.stub(Backbone.history, 'start').callsFake(sinon.spy());
            sinon.stub(Backbone.history, 'getFragment').callsFake(function () {
                return JSON.stringify(currentUrl);
            });

            stubs.queryFormplayer = sinon.stub(API, 'queryFormplayer').callsFake(function (options, route) {
                return {success: 1};
            });

            // Prevent showing views, which doesn't work properly in tests
            FormplayerFrontend.off("before:start");
            FormplayerFrontend.regions = {
                getRegion: function () {
                    return {
                        show: function () { return; },
                        empty: function () { return; },
                    };
                },
            };

            // Note this calls queryFormplayer
            FormplayerFrontend.getChannel().request("app:select:menus", {
                isInitial: true,    // navigate_menu_start
            });
        });

        afterEach(function () {
            Backbone.history.getFragment.restore();
            Util.currentUrlToObject.restore();
            Util.setUrlToObject.restore();
            API.queryFormplayer.restore();
            Backbone.history.start.restore();
        });

        // Get route of the most recent call to queryFormplayer
        var getLastRoute = function () {
            if (!stubs.queryFormplayer) {
                return null;
            }
            return _.last(stubs.queryFormplayer.args)[1];   // second arg passed to the latest call
        };

        it("should navigate to a form", function () {
            FormplayerFrontend.trigger("menu:select", 0);

            var url = Util.currentUrlToObject();
            assert.deepEqual(url.selections, ['0']);
            assert.isNotOk(url.queryData);
            assert.isNotOk(url.search);
            assert.equal(url.appId, 'abc123');
            assert.isTrue(stubs.queryFormplayer.calledTwice);
            assert.equal(getLastRoute(), "navigate_menu");

            FormplayerFrontend.trigger("menu:select", 0);
            var url = Util.currentUrlToObject();
            assert.deepEqual(url.selections, ['0', '0']);
            assert.isNotOk(url.queryData);
            assert.isNotOk(url.search);
            assert.equal(url.appId, 'abc123');
            assert.isTrue(stubs.queryFormplayer.calledThrice);
            assert.equal(getLastRoute(), "navigate_menu");
        });

        it("should select a case", function () {
            FormplayerFrontend.trigger("menu:select", 1);
            FormplayerFrontend.trigger("menu:select", 'some_case_id');
            var url = Util.currentUrlToObject();
            assert.deepEqual(url.selections, ['1', 'some_case_id']);
            assert.isNotOk(url.queryData);
            assert.isNotOk(url.search);
            assert.isTrue(stubs.queryFormplayer.calledThrice);
            assert.equal(getLastRoute(), "navigate_menu");
        });
    });
});
