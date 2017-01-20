/*eslint-env mocha */
/*global _ */

describe('Location Types', function() {

    var LocationSettingsViewModel = hqImport('locations/js/location_types.js').LocationSettingsViewModel,
        LocationTypeModel = hqImport('locations/js/location_types.js').LocationTypeModel;

    var extract_name = function(loc_type){
        return loc_type.name();
    };

    describe('Linear Hierarchy', function(){
        var data = hqImport('locations/spec/data/locations_data.js').linear;

        beforeEach(function(){
            this.location_types = _.map(data, function(data){
                return _.clone(data); // we mutate these values later
            });
            this.view_model = new LocationSettingsViewModel(this.location_types, false),
            this.state_model = new LocationTypeModel(data.state, false, this.view_model),
            this.district_model = new LocationTypeModel(data.district, false, this.view_model),
            this.block_model = new LocationTypeModel(data.block, false, this.view_model),
            this.supervisor_model = new LocationTypeModel(data.supervisor, false, this.view_model);
        });

        var make_cycle = function(){
            this.location_types[0].parent_type = data.block.pk; // state.parent_type = block
            this.state_model.parent_type(this.block_model.pk);
            this.view_model = new LocationSettingsViewModel(this.location_types, false);

            this.state_model.view = this.view_model;
            this.district_model.view = this.view_model;
            this.block_model.view = this.view_model;
            this.supervisor_model.view = this.view_model;
        };

        describe('expand_from_options', function() {
            it('Provides all levels down to the current one, including root', function() {
                var returned_loc_types = _.map(
                    this.block_model.expand_from_options(),
                    extract_name
                ),
                    desired_loc_types_returned = _.map([this.state_model, this.district_model], extract_name);
                desired_loc_types_returned.push('root');
                assert.sameMembers(desired_loc_types_returned, returned_loc_types);
            });

            it('Returns only root if there are cycles', function(){
                make_cycle.call(this);
                var returned_loc_types = _.map(this.state_model.expand_from_options(), extract_name);
                assert(this.view_model.has_cycles());
                assert.sameMembers(['root'], returned_loc_types);
            });
        });

        describe('expand_to_options', function() {
            it('Provides all levels beneath the current one', function(){
                var returned_loc_types = _.map(this.district_model.expand_to_options().children, extract_name),
                    desired_loc_types_returned = _.map([this.district_model, this.block_model], extract_name);
                assert.isFalse(this.view_model.has_cycles());
                assert.sameMembers(desired_loc_types_returned, returned_loc_types);
            });

            it('Returns the outermost leaf', function(){
                var leaf = this.district_model.expand_to_options().leaf.name();
                assert.equal(leaf, 'supervisor');
            });

            it ('Returns empty if there are cycles', function(){
                make_cycle.call(this);
                var returned_loc_types = _.map(this.state_model.expand_to_options().children, extract_name);
                assert(this.view_model.has_cycles());
                assert.sameMembers([], returned_loc_types);
            });

        });

        describe('include_without_expanding_options', function(){
            it('Provides all levels above itself', function(){
                var returned_loc_types = _.map(
                    this.block_model.include_without_expanding_options(),
                    extract_name
                ),
                    desired_loc_types_returned = _.map([this.state_model, this.district_model, this.block_model], extract_name);
                assert.sameMembers(desired_loc_types_returned, returned_loc_types);
            });

            it('Provides nothing if expand from is root', function(){
                this.block_model.expand_from(-1);
                var returned_loc_types = _.map(
                    this.block_model.include_without_expanding_options(),
                    extract_name
                );
                assert.equal(0, returned_loc_types.length);
            });
        });
    });

    describe('Forked Hierarchy', function(){
        var data = hqImport('locations/spec/data/locations_data.js').forked;

        beforeEach(function(){
            this.location_types = _.map(data, function(data){
                return _.clone(data); // we mutate these values later
            });
            this.view_model = new LocationSettingsViewModel(this.location_types, false),
            this.state_model = new LocationTypeModel(data.state, false, this.view_model),
            this.county_model = new LocationTypeModel(data.county, false, this.view_model),
            this.city_model = new LocationTypeModel(data.city, false, this.view_model),
            this.region_model = new LocationTypeModel(data.region, false, this.view_model);
            this.town_model = new LocationTypeModel(data.town, false, this.view_model);
        });

        describe('expand_to_options', function(){
            it('shows when types are at the same level', function(){
                var returned_loc_types = this.state_model.expand_to_options(),
                    desired_children_returned = ["state", "county | region"],
                    desired_leaf_returned = "city | town";

                assert.isFalse(this.view_model.has_cycles());
                assert.sameMembers(desired_children_returned, _.map(
                    returned_loc_types.children, extract_name
                ));
                assert.equal(desired_leaf_returned, returned_loc_types.leaf.name());
            });

            it('calculates the correct level', function(){
                assert.equal(this.town_model.level(), 2);
                assert.equal(this.state_model.level(), 0);
                assert.equal(this.city_model.level(), 2);
            });
        });
    });

});
