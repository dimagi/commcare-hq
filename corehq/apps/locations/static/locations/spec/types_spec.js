/*eslint-env mocha */
/*global LocationSettingsViewModel, LocationTypeModel, _, state, district, block, supervisor */

describe('Location Types', function() {

    var location_types = [state, district, block, supervisor],
        view_model = new LocationSettingsViewModel(location_types, false),
        state_model = new LocationTypeModel(state),
        district_model = new LocationTypeModel(district),
        block_model = new LocationTypeModel(block),
        supervisor_model = new LocationTypeModel(supervisor);

    var extract_name = function(loc_type){
        return loc_type.name();
    };

    describe('expand_from_options', function() {
        it('Provides all levels down to the current one, including root', function() {
            var returned_loc_types = _.map(view_model.expand_from_options(block_model), extract_name),
                desired_loc_types_returned = _.map([state_model, district_model, block_model], extract_name);
            desired_loc_types_returned.push('root');
            assert.sameMembers(desired_loc_types_returned, returned_loc_types);
        });

        it('Returns only itself and root if there are cycles', function(){
            // make a cycle
            state.parent_type = block.pk;
            state_model.parent_type(block_model.pk);
            view_model = new LocationSettingsViewModel(location_types, false);
            var returned_loc_types = _.map(view_model.expand_from_options(state_model), extract_name);
            assert(view_model.has_cycles());
            assert.sameMembers([state_model.name(), 'root'], returned_loc_types);
        });
    });

    describe('expand_to_options', function() {
        it('Provides all levels beneath the current one', function(){
            var returned_loc_types = _.map(view_model.expand_to_options(district_model), extract_name),
                desired_loc_types_returned = _.map([district_model, block_model, supervisor_model], extract_name);
            assert.sameMembers(desired_loc_types_returned, returned_loc_types);
        });

    });
});
