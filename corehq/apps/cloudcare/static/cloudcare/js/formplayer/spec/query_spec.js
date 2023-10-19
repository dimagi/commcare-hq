/* eslint-env mocha */
/* global Backbone */
hqDefine("cloudcare/js/formplayer/spec/query_spec", function () {
    describe('Query', function () {

        describe('itemset', function () {
            let QueryListView = hqImport("cloudcare/js/formplayer/menus/views/query"),
                Utils = hqImport("cloudcare/js/formplayer/utils/utils");

            let QueryViewModel = Backbone.Model.extend(),
                QueryViewCollection = Backbone.Collection.extend(),
                keyModel = new QueryViewModel({
                    "itemsetChoicesKey": ["CA", "MA", "FL"],
                    "itemsetChoices": ["California", "Massachusetts", "Florida"],
                });

            let keyViewCollection = new QueryViewCollection([keyModel])

            sinon.stub(Utils, 'getStickyQueryInputs').callsFake(function () { return 'fake_value'; });
            let keyQueryListView =  QueryListView({ collection: keyViewCollection}),
                keyQueryView = new keyQueryListView.childView({ parentView: keyQueryListView, model: keyModel})

            it('should create dictionary with either keys', function () {
                let expectedKeyItemsetChoicesDict = { "CA": "California", "MA": "Massachusetts", "FL": "Florida"};
                assert.deepEqual(expectedKeyItemsetChoicesDict, keyQueryView.model.get("itemsetChoicesDict"));
            });
        });
    });
});
