/* eslint-env mocha */
/* global Backbone */

describe('Query', function () {

    describe('itemset', function () {
        let QueryListView = hqImport("cloudcare/js/formplayer/menus/views/query"),
            Utils = hqImport("cloudcare/js/formplayer/utils/utils");

        let QueryViewModel = Backbone.Model.extend(),
            QueryViewCollection = Backbone.Collection.extend(),
            keyModel = new QueryViewModel({
                "itemsetChoicesKey": ["CA", "MA", "FL"],
                "itemsetChoices": ["California", "Massachusetts", "Florida"],
            }),
            indexModel = new QueryViewModel({
                "itemsetChoices": ["California", "Massachusetts", "Florida"],
            })

        let keyViewCollection = new QueryViewCollection([keyModel]),
            indexViewCollection = new QueryViewCollection([indexModel])

        sinon.stub(Utils, 'getStickyQueryInputs').callsFake(function () { return 'fake_value'; });
        let keyQueryListView =  QueryListView({collection:keyViewCollection}),
            keyQueryView = new keyQueryListView.childView({parentView:keyQueryListView, model: keyModel}),
            indexQueryListView =  QueryListView({collection:indexViewCollection}),
            indexQueryView = new keyQueryListView.childView({parentView:indexQueryListView, model: indexModel});

        it('should flag if options contains keys for itemset', function () {
            assert.isTrue(keyQueryListView.selectValuesByKeys)
            assert.isFalse(indexQueryListView.selectValuesByKeys)
        });

        it('should create dictionary with either keys if provided. Otherwise, with index as the key', function() {
            expected_keyItemsetChoicesDict = {"CA":"California", "MA":"Massachusetts", "FL":"Florida"}
            assert.deepEqual(expected_keyItemsetChoicesDict, keyQueryView.model.get("itemsetChoicesDict"))

            expected_indexItemsetChoicesDict = {"0":"California", "1":"Massachusetts", "2":"Florida"}
            assert.deepEqual(expected_indexItemsetChoicesDict, indexQueryView.model.get("itemsetChoicesDict"))

        });
    });
});
