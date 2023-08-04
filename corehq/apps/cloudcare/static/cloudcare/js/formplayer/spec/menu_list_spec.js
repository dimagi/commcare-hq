/* global Backbone */
/* eslint-env mocha */
hqDefine("cloudcare/js/formplayer/spec/menu_list_spec", function () {
    describe('Render a case list', function () {
        let MenuListFixture = hqImport("cloudcare/js/formplayer/spec/fixtures/menu_list"),
            Utils = hqImport("cloudcare/js/formplayer/utils/utils");

        before(function () {
            hqImport("hqwebapp/js/initial_page_data").register(
                "toggles_dict",
                {
                    CHANGE_FORM_LANGUAGE: false,
                    SPLIT_SCREEN_CASE_SEARCH: false,
                }
            );
            sinon.stub(Utils, 'getCurrentQueryInputs').callsFake(function () { return {}; });
        });

        describe('#getMenuView', function () {
            let FormplayerFrontend = hqImport("cloudcare/js/formplayer/app"),
                server,
                user;
            beforeEach(function () {
                server = sinon.useFakeXMLHttpRequest();
                sinon.stub(Backbone.history, 'getFragment').callsFake(sinon.spy());

                user = FormplayerFrontend.getChannel().request('currentUser');
                user.displayOptions = {
                    singleAppMode: false,
                };
            });

            afterEach(function () {
                server.restore();
                Backbone.history.getFragment.restore();
            });

            let getMenuView = hqImport("cloudcare/js/formplayer/menus/utils").getMenuView;
            it('Should parse a case list response to a CaseListView', function () {
                let view = getMenuView(hqImport("cloudcare/js/formplayer/spec/fixtures/case_list"));
                assert.isFalse(view.templateContext().useTiles);
            });

            it('Should parse a menu list response to a MenuListView', function () {
                let view = getMenuView(MenuListFixture);
                assert.isTrue(view.childViewContainer === ".menus-container");
            });

            it('Should parse a case list response with tiles to a CaseTileListView', function () {
                let view = getMenuView(hqImport("cloudcare/js/formplayer/spec/fixtures/case_tile_list"));
                assert.isTrue(view.templateContext().useTiles);
            });

            it('Should parse a case grid response with tiles to a GridCaseTileListView', function () {
                let view = getMenuView(hqImport("cloudcare/js/formplayer/spec/fixtures/case_grid_list"));
                assert.isTrue(view.templateContext().useTiles);
            });
        });

        describe('#getMenus', function () {
            let FormplayerFrontend = hqImport("cloudcare/js/formplayer/app"),
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

                sinon.stub(Backbone.history, 'getFragment').callsFake(sinon.spy());

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

                hqImport("cloudcare/js/formplayer/apps/api").primeApps(user.restoreAs, []);
            });

            afterEach(function () {
                server.restore();
                clock.restore();
                Backbone.history.getFragment.restore();
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
                    JSON.stringify(MenuListFixture)
                );

                clock.tick(1); // click 1 forward to ensure that we've fired off the empty progress

                // We should have emptied the progress bar
                assert.isTrue(currentView === undefined);
            });

            it('Should execute an async restore', function () {
                let promise = FormplayerFrontend.getChannel().request('app:select:menus', {
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
                    JSON.stringify(MenuListFixture)
                );

                clock.tick(1); // click 1 forward to ensure that we've fired off the empty progress

                // We should have emptied the progress bar
                assert.isTrue(currentView === undefined);
                assert.equal(promise.state(), 'resolved');  // We have now completed the restore
            });
        });
    });
});
