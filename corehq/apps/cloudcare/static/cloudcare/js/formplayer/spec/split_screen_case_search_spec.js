/* eslint-env mocha sinon */
/* global Backbone, Marionette */

describe('Split Screen Case Search', function () {
    const API = hqImport("cloudcare/js/formplayer/menus/api"),
        Controller = hqImport('cloudcare/js/formplayer/menus/controller'),
        FakeFormplayer = hqImport('cloudcare/js/formplayer/spec/fake_formplayer'),
        FormplayerFrontend = hqImport('cloudcare/js/formplayer/app'),
        splitScreenCaseListResponse = hqImport('cloudcare/js/formplayer/spec/fixtures/split_screen_case_list'),
        Toggles = hqImport('hqwebapp/js/toggles'),
        Utils = hqImport('cloudcare/js/formplayer/utils/utils');

    const currentUrl = new Utils.CloudcareUrl({ appId: 'abc123' }),
        sandbox = sinon.sandbox.create(),
        clearSidebar = sandbox.spy(currentUrl, 'clearSidebar'),
        stubs = {},
        REGIONS = {
            main: 'main',
            sidebar: 'sidebar',
        };

    let getRegion;

    before(function () {
        sandbox.stub(Marionette.CollectionView.prototype, 'render').returns();
        sandbox.stub(Utils, 'currentUrlToObject').callsFake(function () {
            return currentUrl;
        });

        sandbox.stub(Backbone.history, 'start').callsFake(sandbox.spy());
        sandbox.stub(Backbone.history, 'getFragment').callsFake(function () {
            return JSON.stringify(currentUrl);
        });
        sandbox.stub(API, 'queryFormplayer').callsFake(FakeFormplayer.queryFormplayer);

        stubs.show = sandbox.stub().callsFake(function () { return; });
        stubs.empty = sandbox.stub().callsFake(function () { return; });
        FormplayerFrontend.regions = {
            getRegion: function (region) {
                return {
                    region: region,
                    show: stubs.show,
                    empty: stubs.empty,
                };
            },
            addRegions: function () { return; },
        };
        getRegion = sandbox.spy(FormplayerFrontend.regions, 'getRegion');
        stubs.splitScreenToggleEnabled = sandbox.stub(Toggles, 'toggleEnabled').withArgs('SPLIT_SCREEN_CASE_SEARCH');
    });

    beforeEach(function () {
        FormplayerFrontend.currentUser.displayOptions.singleAppMode = false;
        stubs.splitScreenToggleEnabled.returns(true);
    });

    afterEach(function () {
        getRegion.reset();
        clearSidebar.reset();
        sandbox.resetHistory();
    });

    after(function () {
        sandbox.restore();
    });

    describe('Controller actions', function () {
        it('should show sidebar and main regions with entities type split screen case search', function () {
            Controller.showMenu(splitScreenCaseListResponse);

            assert.isTrue(getRegion.calledWith(REGIONS.sidebar));
            assert.isTrue(_.some(stubs.show.getCalls(), call => call.thisValue.region === REGIONS.sidebar));

            assert.isTrue(getRegion.calledWith(REGIONS.main));
            assert.isTrue(_.some(stubs.show.getCalls(), call => call.thisValue.region === REGIONS.main));
        });

        it('should show sidebar and main regions with query type split screen case search', function () {
            const responseWithTypeQuery = _.extend({}, splitScreenCaseListResponse, { 'type': 'query' });
            Controller.showMenu(responseWithTypeQuery);

            assert.isTrue(getRegion.calledWith(REGIONS.main));
            assert.isTrue(_.some(stubs.show.getCalls(), call => call.thisValue.region === REGIONS.main));

            assert.isTrue(getRegion.calledWith(REGIONS.sidebar));
            assert.isTrue(_.some(stubs.show.getCalls(), call => call.thisValue.region === REGIONS.sidebar));
        });

        it('should explicitly set sidebarEnabled and triggerEmptyCaseList with query type split screen case search', function () {
            const responseWithTypeQuery = _.extend({}, splitScreenCaseListResponse, { 'type': 'query' });
            Controller.showMenu(responseWithTypeQuery);

            const showMain = _.find(stubs.show.getCalls(), call => call.thisValue.region === REGIONS.main);
            assert.isTrue(showMain.args[0].options.sidebarEnabled);
            assert.isTrue(showMain.args[0].options.triggerEmptyCaseList);
        });

        it('should empty sidebar if in app preview', function () {
            FormplayerFrontend.currentUser.displayOptions.singleAppMode = true;
            Controller.showMenu(splitScreenCaseListResponse);

            assert.isTrue(getRegion.calledWith(REGIONS.sidebar));
            assert.isTrue(_.some(stubs.empty.getCalls(), call => call.thisValue.region === REGIONS.sidebar));
        });

        it('should empty sidebar if response type neither entities nor query', function () {
            const responseWithTypeEmpty = _.extend({}, splitScreenCaseListResponse, { 'type': '' });
            Controller.showMenu(responseWithTypeEmpty);

            assert.isTrue(getRegion.calledWith(REGIONS.sidebar));
            assert.isTrue(_.some(stubs.empty.getCalls(), call => call.thisValue.region === REGIONS.sidebar));
        });

        it('should empty sidebar if no queryResponse present', function () {
            const responseWithoutQueryResponse = _.omit(splitScreenCaseListResponse, 'queryResponse');
            Controller.showMenu(responseWithoutQueryResponse);

            assert.isTrue(getRegion.calledWith(REGIONS.sidebar));
            assert.isTrue(_.some(stubs.empty.getCalls(), call => call.thisValue.region === REGIONS.sidebar));
        });

        it('should empty sidebar if feature flag disabled', function () {
            stubs.splitScreenToggleEnabled.returns(false);
            Controller.showMenu(splitScreenCaseListResponse);

            assert.isTrue(getRegion.calledWith(REGIONS.sidebar));
            assert.isTrue(_.some(stubs.empty.getCalls(), call => call.thisValue.region === REGIONS.sidebar));
        });
    });

    describe('FormplayerFrontend actions', function () {
        it('should clear sidebar on menu:select', function () {
            FormplayerFrontend.trigger('menu:select', 0);

            assert.isTrue(clearSidebar.calledOnce);
        });

        it('should clear sidebar on navigateHome', function () {
            FormplayerFrontend.trigger('navigateHome');

            assert.isTrue(clearSidebar.calledOnce);
        });
    });
});
