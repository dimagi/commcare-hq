/* eslint-env mocha */

describe('Util', function () {
    var API = hqImport("cloudcare/js/formplayer/menus/api"),
        FakeFormplayer = hqImport("cloudcare/js/formplayer/spec/fake_formplayer"),
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

            stubs.queryFormplayer = sinon.stub(API, 'queryFormplayer').callsFake(FakeFormplayer.queryFormplayer);

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
                appId: 'abc123',
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

        it("should navigate to a form", function () {
            FormplayerFrontend.trigger("menu:select", 0);
            var url = Util.currentUrlToObject();
            assert.deepEqual(url.selections, ['0']);
            assert.isNotOk(url.queryData);
            assert.isNotOk(url.search);
            assert.equal(url.appId, 'abc123');
            assert.isTrue(stubs.queryFormplayer.calledTwice);
            var lastCall = stubs.queryFormplayer.lastCall;
            assert.equal(lastCall.args[1], "navigate_menu");
            assert.equal(lastCall.returnValue.title, "Survey Menu");

            FormplayerFrontend.trigger("menu:select", 0);
            var url = Util.currentUrlToObject();
            assert.deepEqual(url.selections, ['0', '0']);
            assert.isNotOk(url.queryData);
            assert.isNotOk(url.search);
            assert.equal(url.appId, 'abc123');
            assert.isTrue(stubs.queryFormplayer.calledThrice);
            var lastCall = stubs.queryFormplayer.lastCall;
            assert.equal(lastCall.args[1], "navigate_menu");
            assert.equal(lastCall.returnValue.title, "Survey Form");
            assert.deepEqual(lastCall.returnValue.breadcrumbs, ["My App", "Survey Menu", "Survey Form"]);
        });

        it("should select a case", function () {
            FormplayerFrontend.trigger("menu:select", 1);
            assert.isTrue(stubs.queryFormplayer.calledTwice);
            var lastCall = stubs.queryFormplayer.lastCall;
            assert.equal(lastCall.args[1], "navigate_menu");
            assert.deepEqual(lastCall.returnValue.breadcrumbs, ["My App", "Some Cases"]);
            assert.equal(lastCall.returnValue.type, "entities");

            FormplayerFrontend.trigger("menu:select", 'some_case_id');
            var url = Util.currentUrlToObject();
            assert.deepEqual(url.selections, ['1', 'some_case_id']);
            assert.isNotOk(url.queryData);
            assert.isNotOk(url.search);
            assert.isTrue(stubs.queryFormplayer.calledThrice);
            var lastCall = stubs.queryFormplayer.lastCall;
            assert.equal(lastCall.args[1], "navigate_menu");
            assert.deepEqual(lastCall.returnValue.breadcrumbs, ["My App", "Some Cases", "Some Case"]);
            assert.equal(lastCall.returnValue.type, "commands");
        });

        it("should navigate to breadcrumb", function () {
            FormplayerFrontend.trigger("menu:select", 0);
            FormplayerFrontend.trigger("menu:select", 0);
            FormplayerFrontend.trigger("breadcrumbSelect", 1);
            var url = Util.currentUrlToObject();
            assert.deepEqual(url.selections, ['0']);
            var lastCall = stubs.queryFormplayer.lastCall;
            assert.equal(lastCall.returnValue.title, "Survey Menu");
            assert.deepEqual(lastCall.returnValue.breadcrumbs, ["My App", "Survey Menu"]);
        });

        it("should navigate to breadcrumb with case", function () {
            FormplayerFrontend.trigger("menu:select", 1);
            FormplayerFrontend.trigger("menu:select", 'some_case_id');
            FormplayerFrontend.trigger("breadcrumbSelect", 1);
            var url = Util.currentUrlToObject();
            assert.deepEqual(url.selections, ['1']);
            var lastCall = stubs.queryFormplayer.lastCall;
            assert.equal(lastCall.returnValue.title, "Some Cases");
            assert.deepEqual(lastCall.returnValue.breadcrumbs, ["My App", "Some Cases"]);
        });

        it("should paginate, filter, and sort case lists", function () {
            FormplayerFrontend.trigger("menu:select", 1);
            FormplayerFrontend.trigger("menu:perPageLimit", 2);
            var url = Util.currentUrlToObject();
            assert.equal(url.casesPerPage, 2);
            assert.equal(url.page, null);
            assert.equal(url.search, null);
            assert.equal(url.sortIndex, null);

            FormplayerFrontend.trigger("menu:search", "x");
            url = Util.currentUrlToObject();
            assert.equal(url.casesPerPage, 2);
            assert.equal(url.page, null);
            assert.equal(url.search, "x");
            assert.equal(url.sortIndex, null);

            FormplayerFrontend.trigger("menu:paginate", 1);
            url = Util.currentUrlToObject();
            assert.equal(url.casesPerPage, 2);
            assert.equal(url.page, 1);
            assert.equal(url.search, "x");
            assert.equal(url.sortIndex, null);

            FormplayerFrontend.trigger("menu:sort", 2);
            url = Util.currentUrlToObject();
            assert.equal(url.casesPerPage, 2);
            assert.equal(url.page, 1);
            assert.equal(url.search, "x");
            assert.equal(url.sortIndex, 2);
        });

        it("should clear pagination on search", function () {
            FormplayerFrontend.trigger("menu:select", 1);
            FormplayerFrontend.trigger("menu:perPageLimit", 2);
            FormplayerFrontend.trigger("menu:paginate", 1);
            FormplayerFrontend.trigger("menu:sort", 2);
            FormplayerFrontend.trigger("menu:search", "y");
            url = Util.currentUrlToObject();
            assert.equal(url.casesPerPage, 2);
            assert.equal(url.page, null);
            assert.equal(url.search, "y");
            assert.equal(url.sortIndex, null);
        });

        it("should clear pagination and search on selecting a case", function () {
            FormplayerFrontend.trigger("menu:select", 1);
            FormplayerFrontend.trigger("menu:perPageLimit", 2);
            FormplayerFrontend.trigger("menu:paginate", 1);
            FormplayerFrontend.trigger("menu:sort", 2);
            FormplayerFrontend.trigger("menu:search", "z");
            FormplayerFrontend.trigger("menu:select", 'some_case_id');
            url = Util.currentUrlToObject();
            assert.equal(url.casesPerPage, 2);
            assert.equal(url.page, null);
            assert.equal(url.search, null);
            assert.equal(url.sortIndex, null);
        });
    });
});
