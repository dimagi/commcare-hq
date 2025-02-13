import _ from "underscore";
import Backbone from "backbone";
import Marionette from "backbone.marionette";
import sinon from "sinon";
import Toggles from "hqwebapp/js/toggles";
import FormplayerFrontend from "cloudcare/js/formplayer/app";
import API from "cloudcare/js/formplayer/menus/api";
import Controller from "cloudcare/js/formplayer/menus/controller";
import FakeFormplayer from "cloudcare/js/formplayer/spec/fake_formplayer";
import splitScreenCaseListResponse from "cloudcare/js/formplayer/spec/fixtures/split_screen_case_list";
import Utils from "cloudcare/js/formplayer/utils/utils";
import UsersModels from "cloudcare/js/formplayer/users/models";

describe('Split Screen Case Search', function () {
    const currentUrl = new Utils.CloudcareUrl({ appId: 'abc123' }),
        stubs = {};

    before(function () {
        sinon.stub(Marionette.CollectionView.prototype, 'render').returns();
        sinon.stub(Utils, 'currentUrlToObject').callsFake(function () {
            return currentUrl;
        });

        sinon.stub(Backbone.history, 'start').callsFake(sinon.spy());
        sinon.stub(Backbone.history, 'getFragment').callsFake(function () {
            return JSON.stringify(currentUrl);
        });
        sinon.stub(API, 'queryFormplayer').callsFake(FakeFormplayer.queryFormplayer);

        stubs.regions = {};
        FormplayerFrontend.regions = {
            getRegion: function (region) {
                if (!_.has(stubs.regions, region)) {
                    stubs.regions[region] = {
                        region: region,
                        show: sinon.stub().callsFake(function () { return; }),
                        empty: sinon.stub().callsFake(function () { return; }),
                    };
                }
                return stubs.regions[region];
            },
            addRegions: function () { return; },
        };
        stubs.splitScreenToggleEnabled = sinon.stub(Toggles, 'toggleEnabled').withArgs('SPLIT_SCREEN_CASE_SEARCH');
    });

    beforeEach(function () {
        var user = UsersModels.getCurrentUser();
        user.displayOptions = {
            singleAppMode: false,
        };
        stubs.splitScreenToggleEnabled.returns(true);
    });

    afterEach(function () {
        sinon.resetHistory();
    });

    after(function () {
        sinon.restore();
    });

    describe('Controller actions', function () {
        it('should show sidebar and main regions with entities type split screen case search', function () {
            Controller.showMenu(splitScreenCaseListResponse);

            assert.isTrue(stubs.regions['sidebar'].show.called);
            assert.isTrue(stubs.regions['main'].show.called);
            assert.isTrue(stubs.regions['breadcrumbMenuDropdown'].show.called);
        });

        it('should show sidebar and main regions with query type split screen case search', function () {
            const responseWithTypeQuery = _.extend(
                {},
                splitScreenCaseListResponse,
                { 'type': 'query'},
                new Backbone.Collection(splitScreenCaseListResponse.queryResponse.displays));
            Controller.showMenu(responseWithTypeQuery);

            assert.isTrue(stubs.regions['sidebar'].show.called);
            assert.isTrue(stubs.regions['main'].show.called);
        });

        it('should explicitly set sidebarEnabled and triggerEmptyCaseList with query type split screen case search', function () {
            const responseWithTypeQuery = _.extend(
                {},
                splitScreenCaseListResponse,
                { 'type': 'query'},
                new Backbone.Collection(splitScreenCaseListResponse.queryResponse.displays));
            Controller.showMenu(responseWithTypeQuery);

            assert.isTrue(stubs.regions['main'].show.called);
            var showMain = stubs.regions['main'].show.getCalls()[0];
            assert.isTrue(showMain.args[0].options.sidebarEnabled);
            assert.isTrue(showMain.args[0].options.triggerEmptyCaseList);
        });

        it('should hide sidebar if there are no search inputs in query response', function () {
            const responseWithTypeQuery = _.extend(
                {},
                splitScreenCaseListResponse,
                { 'type': 'query'},
                new Backbone.Collection([]));
            Controller.showMenu(responseWithTypeQuery);

            assert.isTrue(stubs.regions['sidebar'].empty.called);
        });

        it('should hide sidebar if there are no search inputs in entities response', function () {
            let queryResponse = splitScreenCaseListResponse.queryResponse;
            queryResponse = _.extend({}, queryResponse, {'displays': {}});
            const responseWithTypeQuery = _.extend({}, splitScreenCaseListResponse, {'queryResponse': queryResponse});
            Controller.showMenu(responseWithTypeQuery);

            assert.isTrue(stubs.regions['sidebar'].empty.called);
        });

        it('should empty sidebar if in app preview', function () {
            var user = UsersModels.getCurrentUser();
            user.displayOptions = {
                singleAppMode: true,
            };
            Controller.showMenu(splitScreenCaseListResponse);

            assert.isTrue(stubs.regions['sidebar'].empty.called);
        });

        it('should empty sidebar if response type neither entities nor query', function () {
            const responseWithTypeEmpty = _.extend({}, splitScreenCaseListResponse, { 'type': '' });
            Controller.showMenu(responseWithTypeEmpty);

            assert.isTrue(stubs.regions['sidebar'].empty.called);
        });

        it('should empty sidebar if no queryResponse present', function () {
            const responseWithoutQueryResponse = _.omit(splitScreenCaseListResponse, 'queryResponse');
            Controller.showMenu(responseWithoutQueryResponse);

            assert.isTrue(stubs.regions['sidebar'].empty.called);
        });

        it('should empty sidebar if feature flag disabled', function () {
            stubs.splitScreenToggleEnabled.returns(false);
            Controller.showMenu(splitScreenCaseListResponse);

            assert.isTrue(stubs.regions['sidebar'].empty.called);
        });
    });

    describe('FormplayerFrontend actions', function () {
        it('should clear sidebar on menu:select', function () {
            assert.isFalse(stubs.regions['sidebar'].empty.called);
            FormplayerFrontend.trigger('menu:select', 0);
            assert.isTrue(stubs.regions['sidebar'].empty.called);
        });

        it('should clear sidebar on navigateHome', function () {
            assert.isFalse(stubs.regions['sidebar'].empty.called);
            FormplayerFrontend.trigger('navigateHome');
            assert.isTrue(stubs.regions['sidebar'].empty.called);
        });
    });
});
