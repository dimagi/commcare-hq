/* global Backbone */
/* eslint-env mocha */
describe('Render a case list', function () {
    var fixtures = hqImport("cloudcare/js/formplayer/spec/fixtures"),
        Util = hqImport("cloudcare/js/formplayer/utils/util");

    before(function () {
        hqImport("hqwebapp/js/initial_page_data").register(
            "toggles_dict",
            {
                APP_ANALYTICS: true,
            }
        );
        sinon.stub(Util, 'getCurrentQueryInputs').callsFake(function () { return {}; });
    });

    describe('#getMenuView', function () {
        var server;
        beforeEach(function () {
            server = sinon.useFakeXMLHttpRequest();
            sinon.stub(Backbone.history, 'getFragment').callsFake(sinon.spy());
        });

        afterEach(function () {
            server.restore();
            Backbone.history.getFragment.restore();
        });

        var getMenuView = hqImport("cloudcare/js/formplayer/menus/util").getMenuView;
        it('Should parse a case list response to a CaseListView', function () {
            var view = getMenuView(fixtures.caseList);
            assert.isFalse(view.templateContext().useTiles);
            assert.isFalse(view.templateContext().useGrid);
        });

        it('Should parse a menu list response to a MenuListView', function () {
            var view = getMenuView(fixtures.menuList);
            assert.isTrue(view.childViewContainer === ".menus-container");
        });

        it('Should parse a case list response with tiles to a CaseTileListView', function () {
            var view = getMenuView(fixtures.caseTileList);
            assert.isTrue(view.templateContext().useTiles);
            assert.isFalse(view.templateContext().useGrid);
        });

        it('Should parse a case grid response with tiles to a GridCaseTileListView', function () {
            var view = getMenuView(fixtures.caseGridList);
            assert.isTrue(view.templateContext().useTiles);
            assert.isTrue(view.templateContext().useGrid);
        });
    });

    describe('#getMenus', function () {
        var FormplayerFrontend = hqImport("cloudcare/js/formplayer/app"),
            server,
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
            user = FormplayerFrontend.getChannel().request('currentUser');
            user.domain = 'test-domain';
            user.username = 'test-username';
            user.formplayer_url = 'url';
            user.restoreAs = '';
            user.displayOptions = {};

            hqImport("cloudcare/js/formplayer/apps/api").primeApps(user.restoreAs, new Backbone.Collection());
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
            var promise = FormplayerFrontend.getChannel().request('app:select:menus', {
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
