'use strict';
/* eslint-env mocha */
/* global Backbone */
hqDefine("cloudcare/js/formplayer/spec/query_spec", function () {
    describe('Query', function () {

        describe('itemset', function () {

            let keyQueryView;

            before(function () {
                const QueryListView = hqImport("cloudcare/js/formplayer/menus/views/query");
                const Utils = hqImport("cloudcare/js/formplayer/utils/utils");

                hqImport("hqwebapp/js/initial_page_data").register("toggles_dict", { DYNAMICALLY_UPDATE_SEARCH_RESULTS: false });

                const QueryViewModel = Backbone.Model.extend();
                const QueryViewCollection = Backbone.Collection.extend();
                const keyModel = new QueryViewModel({
                    "itemsetChoicesKey": ["CA", "MA", "FL"],
                    "itemsetChoices": ["California", "Massachusetts", "Florida"],
                    "groupKey": "test",
                });

                const keyViewCollection = new QueryViewCollection([keyModel]);

                sinon.stub(Utils, 'getStickyQueryInputs').callsFake(function () { return 'fake_value'; });

                const keyQueryListView = QueryListView.queryListView({
                    collection: keyViewCollection,
                    groupHeaders: {
                        "test": "Test",
                    },
                });

                const childViewConstructor = keyQueryListView.childView(new Backbone.Model({}));
                keyQueryView = new childViewConstructor({ parentView: keyQueryListView, model: keyModel});
            });

            after(function () {
                hqImport("hqwebapp/js/initial_page_data").unregister("toggles_dict");
            });

            it('should create dictionary with either keys', function () {
                const expectedKeyItemsetChoicesDict = { "CA": "California", "MA": "Massachusetts", "FL": "Florida"};
                assert.deepEqual(expectedKeyItemsetChoicesDict, keyQueryView.model.get("itemsetChoicesDict"));
            });
        });
    });
});
