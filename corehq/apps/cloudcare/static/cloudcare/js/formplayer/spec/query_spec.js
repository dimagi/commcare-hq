/* eslint-env mocha */
/* global Backbone */
hqDefine("cloudcare/js/formplayer/spec/query_spec", function () {
    describe('Query', function () {

        describe('itemset', function () {

            let keyQueryView;

            before(function () {
                const QueryListView = hqImport("cloudcare/js/formplayer/menus/views/query");
                const Utils = hqImport("cloudcare/js/formplayer/utils/utils");

                const QueryViewModel = Backbone.Model.extend();
                const QueryViewCollection = Backbone.Collection.extend();
                const keyModel = new QueryViewModel({
                    "itemsetChoicesKey": ["CA", "MA", "FL"],
                    "itemsetChoices": ["California", "Massachusetts", "Florida"],
                });

                const keyViewCollection = new QueryViewCollection([keyModel]);

                sinon.stub(Utils, 'getStickyQueryInputs').callsFake(function () { return 'fake_value'; });

                const keyQueryListView = QueryListView({ collection: keyViewCollection});
                keyQueryView = new keyQueryListView.childView({ parentView: keyQueryListView, model: keyModel});
            });

            it('should create dictionary with either keys', function () {
                const expectedKeyItemsetChoicesDict = { "CA": "California", "MA": "Massachusetts", "FL": "Florida"};
                assert.deepEqual(expectedKeyItemsetChoicesDict, keyQueryView.model.get("itemsetChoicesDict"));
            });
        });
    });
});
