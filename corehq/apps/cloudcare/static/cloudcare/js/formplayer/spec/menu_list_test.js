/* global FormplayerFrontend */
/* eslint-env mocha */
describe('Render a case list', function () {
    var MenuList = FormplayerFrontend.SessionNavigate.MenuList;
    describe('#getMenuView', function () {
        var fixtures = hqImport("corehq/apps/cloudcare/static/cloudcare/js/formplayer/spec/fixtures.js");

        it('Should parse a case list response to a CaseListView', function () {
            var caseListView = MenuList.Util.getMenuView(fixtures.caseList);
            assert.isTrue(caseListView instanceof MenuList.CaseListView);
        });

        it('Should parse a menu list response to a MenuListView', function () {
            var menuListView = MenuList.Util.getMenuView(fixtures.menuList);
            assert.isTrue(menuListView instanceof MenuList.MenuListView);
        });

        it('Should parse a case list response with tiles to a CaseTileListView', function () {
            var caseTileListView = MenuList.Util.getMenuView(fixtures.caseTileList);
            assert.isTrue(caseTileListView instanceof MenuList.CaseTileListView);
        });

        it('Should parse a case grid response with tiles to a GridCaseTileListView', function () {
            var caseTileGridView = MenuList.Util.getMenuView(fixtures.caseGridList);
            assert.isTrue(caseTileGridView instanceof MenuList.GridCaseTileListView);
        });
    });
});