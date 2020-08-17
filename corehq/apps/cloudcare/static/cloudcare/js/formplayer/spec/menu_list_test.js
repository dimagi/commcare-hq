/* global FormplayerFrontend, Backbone */
/* eslint-env mocha */
describe('Render a case list', function () {
    var Menus = FormplayerFrontend.Menus;
    var fixtures = hqImport("cloudcare/js/formplayer/spec/fixtures");
    describe('#getMenuView', function () {
        var server;
        beforeEach(function () {
            server = sinon.useFakeXMLHttpRequest();
        });

        afterEach(function () {
            server.restore();
        });

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

    describe('#getMenus', function () {
        var server,
            clock,
            user,
            requests,
            currentView;

        before(function () {
            hqImport("hqwebapp/js/initial_page_data").register("apps", [{
                "_id": "my-app-id",
            }]);
        });

        beforeEach(function () {
            window.gettext = sinon.spy();

            FormplayerFrontend.regions = {
                getRegion: function (name) {
                    return {
                        show: function () {
                            currentView = name;
                        },
                        empty: function () {
                            currentView = undefined;
                        },
                    };
                },
            };

            requests = [];
            clock = sinon.useFakeTimers();
            server = sinon.useFakeXMLHttpRequest();
            server.onCreate = function (xhr) {
                requests.push(xhr);
            };
            user = FormplayerFrontend.request('currentUser');
            user.domain = 'test-domain';
            user.username = 'test-username';
            user.formplayer_url = 'url';
            user.restoreAs = '';
            user.displayOptions = {};

            FormplayerFrontend.Apps.API.primeApps(user.restoreAs, new Backbone.Collection());
        });

        afterEach(function () {
            server.restore();
            clock.restore();
        });

        it('Should execute an async restore using sync db', function () {
            FormplayerFrontend.trigger('sync');

            // Should have fired off a request for a restore
            assert.equal(requests.length, 1);

            // Send back an async response
            requests[0].respond(
                202,
                { "Content-Type": "application/json" },
                JSON.stringify({
                    "exception": "Asynchronous restore under way for asdf",
                    "done": 9,
                    "total": 30,
                    "retryAfter": 30,
                    "status": "retry",
                    "url": "http://dummy/sync-db",
                    "type": null,
                })
            );

            // We should show loading bar
            assert.isTrue(currentView === "loadingProgress");

            // Fast forward the retry interval of 30 seconds
            clock.tick(30 * 1000);

            // We should have fired off a new request to get the restore again
            assert.equal(requests.length, 2);
            assert.deepEqual(
                JSON.parse(requests[1].requestBody),
                {
                    domain: user.domain,
                    username: user.username,
                    preserveCache: true,
                    restoreAs: '',
                }
            );
            assert.equal(requests[1].url, user.formplayer_url + '/sync-db');
            requests[1].respond(
                200,
                { "Content-Type": "application/json" },
                JSON.stringify(fixtures.menuList)
            );

            clock.tick(1); // click 1 forward to ensure that we've fired off the empty progress

            // We should have emptied the progress bar
            assert.isTrue(currentView === undefined);
        });

        it('Should execute an async restore', function () {
            var promise = FormplayerFrontend.request('app:select:menus', {
                appId: 'my-app-id',
                // Bypass permissions check by using preview mode
                preview: true,
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
            assert.isTrue(currentView === "loadingProgress");
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
            assert.isTrue(currentView === undefined);
            assert.equal(promise.state(), 'resolved');  // We have now completed the restore
        });
    });
});
