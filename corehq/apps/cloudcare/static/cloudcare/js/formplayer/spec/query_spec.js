'use strict';
/* eslint-env mocha */
hqDefine("cloudcare/js/formplayer/spec/query_spec", [
    "backbone",
    "sinon/pkg/sinon",
    "hqwebapp/js/initial_page_data",
    "cloudcare/js/formplayer/utils/utils",
    "cloudcare/js/formplayer/menus/views/query",
], function (
    Backbone,
    sinon,
    initialPageData,
    Utils,
    QueryListView
) {
    describe('Query', function () {
        describe('itemset', function () {

            let keyQueryView;

            before(function () {
                initialPageData.register("toggles_dict", { DYNAMICALLY_UPDATE_SEARCH_RESULTS: false });
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
                initialPageData.unregister("toggles_dict");
            });

            it('should create dictionary with either keys', function () {
                const expectedKeyItemsetChoicesDict = { "CA": "California", "MA": "Massachusetts", "FL": "Florida"};
                assert.deepEqual(expectedKeyItemsetChoicesDict, keyQueryView.model.get("itemsetChoicesDict"));
            });
        });
    });
});
