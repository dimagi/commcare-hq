/*eslint-env mocha */
/*global _ */

describe('Location Types', function() {

    var extract_name = function(loc_type){
        return loc_type.name();
    };

    var data = hqImport('locations/spec/data/locations_data.js'),
        LocationSettingsViewModel = hqImport('locations/ko/location_types.js').LocationSettingsViewModel,
        LocationTypeModel = hqImport('locations/ko/location_types.js').LocationTypeModel;


    beforeEach(function(){
        this.location_types = _.map(data, function(data){
            return _.clone(data); // we mutate these values later
        });
        this.view_model = new LocationSettingsViewModel(this.location_types, false),
        this.state_model = new LocationTypeModel(data.state),
        this.district_model = new LocationTypeModel(data.district),
        this.block_model = new LocationTypeModel(data.block),
        this.supervisor_model = new LocationTypeModel(data.supervisor);
    });

    var make_cycle = function(){
        this.location_types[0].parent_type = data.block.pk; // state.parent_type = block
        this.state_model.parent_type(this.block_model.pk);
        this.view_model = new LocationSettingsViewModel(this.location_types, false);
    };

    describe('expand_from_options', function() {
        it('Provides all levels down to the current one, including root', function() {
            var returned_loc_types = _.map(
                this.view_model.expand_from_options(this.block_model),
                extract_name
            ),
                desired_loc_types_returned = _.map([this.state_model, this.district_model], extract_name);
            desired_loc_types_returned.push('root');
            assert.sameMembers(desired_loc_types_returned, returned_loc_types);
        });

        it('Returns only root if there are cycles', function(){
            make_cycle.call(this);
            var returned_loc_types = _.map(this.view_model.expand_from_options(this.state_model), extract_name);
            assert(this.view_model.has_cycles());
            assert.sameMembers(['root'], returned_loc_types);
        });
    });

    describe('expand_to_options', function() {
        it('Provides all levels beneath the current one', function(){
            var returned_loc_types = _.map(this.view_model.expand_to_options(this.district_model).children, extract_name),
                desired_loc_types_returned = _.map([this.district_model, this.block_model], extract_name);
            assert.isFalse(this.view_model.has_cycles());
            assert.sameMembers(desired_loc_types_returned, returned_loc_types);
        });

        it('Returns the outermost leaf', function(){
            var leaf = this.view_model.expand_to_options(this.district_model).leaf.name();
            assert.equal(leaf, 'supervisor');
        });

        it ('Returns empty if there are cycles', function(){
            make_cycle.call(this);
            var returned_loc_types = _.map(this.view_model.expand_to_options(this.state_model).children, extract_name);
            assert(this.view_model.has_cycles());
            assert.sameMembers([], returned_loc_types);
        });

    });
});
