/* global FormplayerFrontend */
/* eslint-env mocha */
describe('Render a case list', function () {
    var Menus = FormplayerFrontend.Menus;
    var fixtures = hqImport("corehq/apps/cloudcare/static/cloudcare/js/formplayer/spec/fixtures.js");
    describe('#getMenuView', function () {

        it('Should parse a case list response to a CaseListView', function () {
            var caseListView = Menus.Util.getMenuView(fixtures.caseList);
            assert.isTrue(caseListView instanceof Menus.Views.CaseListView);
        });

        it('Should parse a menu list response to a MenuListView', function () {
            var menuListView = Menus.Util.getMenuView(fixtures.menuList);
            assert.isTrue(menuListView instanceof Menus.Views.MenuListView);
        });

        it('Should parse a case list response with tiles to a CaseTileListView', function () {
            var caseTileListView = Menus.Util.getMenuView(fixtures.caseTileList);
            assert.isTrue(caseTileListView instanceof Menus.Views.CaseTileListView);
        });

        it('Should parse a case grid response with tiles to a GridCaseTileListView', function () {
            var caseTileGridView = Menus.Util.getMenuView(fixtures.caseGridList);
            assert.isTrue(caseTileGridView instanceof Menus.Views.GridCaseTileListView);
        });
    });

    describe('#getMenus', function() {
        var server,
            clock,
            requests;

        beforeEach(function() {
            window.gettext = sinon.spy();

            FormplayerFrontend.regions = {
                loadingProgress: {
                    currentView: null,
                    empty: sinon.spy(),
                    show: sinon.spy(),
                },
            };

            requests = [];
            clock = sinon.useFakeTimers();
            server = sinon.useFakeXMLHttpRequest();
            server.onCreate = function (xhr) {
                requests.push(xhr);
            };

        });

        afterEach(function() {
            server.restore();
            clock.restore();
        });

        it('Should execute an async restore', function() {
            var promise = FormplayerFrontend.request('app:select:menus', {
                appId: 'my-app-id',
            });

            // Should have fired off a request for a restore
            assert.equal(requests.length, 1);

            // Send back an async response
            requests[0].respond(
                202,
                { "Content-Type": "application/json" },
                '{"exception":"Asynchronous restore under way for asdf","done":9,"total":30,"retryAfter":30,"status":"retry","url":"http://dummy/navigate_menu","type":null}'
            );

            // We should show loading bar
            assert.isTrue(FormplayerFrontend.regions.loadingProgress.show.called);
            assert.equal(promise.state(), 'pending');

            // Fast forward the retry interval of 30 seconds
            clock.tick(30 * 1000);

            // We should have fired off a new request to get the restore again
            assert.equal(requests.length, 2);
            requests[1].respond(
                200,
                { "Content-Type": "application/json" },
                JSON.stringify(fixtures.menuList)
            );

            clock.tick(1); // click 1 forward to ensure that we've fired off the empty progress

            // We should have emptied the progress bar
            assert.isTrue(FormplayerFrontend.regions.loadingProgress.empty.called);
            assert.equal(promise.state(), 'resolved');  // We have now completed the restore

        });
    });
});
