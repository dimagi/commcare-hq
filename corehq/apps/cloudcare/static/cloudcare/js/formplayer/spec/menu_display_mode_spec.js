import _ from "underscore";
import Marionette from "backbone.marionette";
import sinon from "sinon";
import FormplayerFrontend from "cloudcare/js/formplayer/app";
import Controller from "cloudcare/js/formplayer/menus/controller";
import menusUtils from "cloudcare/js/formplayer/menus/utils";
import UsersModels from "cloudcare/js/formplayer/users/models";

describe('showMenu by display mode', function () {
    const stubs = {};

    const menuResponse = {
        breadcrumbs: ['My App', 'Survey Form'],
        langs: ['en'],
        persistentCaseTile: null,
        persistentMenu: null,
    };

    before(function () {
        sinon.stub(Marionette.CollectionView.prototype, 'render').returns();
        sinon.stub(menusUtils, 'getMenuView').returns(null);
        sinon.stub(menusUtils, 'isSidebarEnabled').returns(false);
        stubs.showBreadcrumbs = sinon.stub(menusUtils, 'showBreadcrumbs');
        stubs.showMenuDropdown = sinon.stub(menusUtils, 'showMenuDropdown');

        stubs.regions = {};
        FormplayerFrontend.regions = {
            getRegion: function (region) {
                if (!_.has(stubs.regions, region)) {
                    stubs.regions[region] = {
                        region: region,
                        show: sinon.stub(),
                        empty: sinon.stub(),
                    };
                }
                return stubs.regions[region];
            },
        };
    });

    afterEach(function () {
        sinon.resetHistory();
    });

    after(function () {
        sinon.restore();
    });

    const showMenuAs = function (displayOptions) {
        UsersModels.getCurrentUser().displayOptions = displayOptions;
        Controller.showMenu(menuResponse);
    };

    it('shows breadcrumbs and the dropdown in normal web apps', function () {
        showMenuAs({singleAppMode: false, publicFormMode: false});

        assert.isTrue(stubs.showBreadcrumbs.called);
        assert.isTrue(stubs.showMenuDropdown.called);
    });

    it('shows breadcrumbs but no dropdown in app preview', function () {
        showMenuAs({singleAppMode: true, publicFormMode: false});

        assert.isTrue(stubs.showBreadcrumbs.called);
        assert.isFalse(stubs.showMenuDropdown.called);
    });

    it('shows the dropdown but no breadcrumbs in a public form', function () {
        showMenuAs({singleAppMode: false, publicFormMode: true});

        assert.isFalse(stubs.showBreadcrumbs.called);
        assert.isTrue(stubs.showMenuDropdown.called);
        assert.isTrue(stubs.regions['breadcrumb'].empty.called);
    });
});
