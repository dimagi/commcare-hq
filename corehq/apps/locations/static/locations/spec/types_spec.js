/*eslint-env mocha */
hqDefine("locations/spec/types_spec", [
    'underscore',
    'locations/spec/data/locations_data',
    'locations/js/location_types',
], function (
    _,
    locationsData,
    locationsTypes
) {
    describe('Location Types', function () {

        var locationSettingsViewModel = locationsTypes.locationSettingsViewModel,
            locationTypeModel = locationsTypes.locationTypeModel;

        var extractName = function (locType) {
            return locType.name();
        };

        describe('Linear Hierarchy', function () {
            var data = locationsData.linear;

            beforeEach(function () {
                this.location_types = _.map(data, function (data) {
                    return _.clone(data); // we mutate these values later
                });
                this.view_model = locationSettingsViewModel(this.location_types, false),
                this.state_model = locationTypeModel(data.state, false, this.view_model),
                this.district_model = locationTypeModel(data.district, false, this.view_model),
                this.block_model = locationTypeModel(data.block, false, this.view_model),
                this.supervisor_model = locationTypeModel(data.supervisor, false, this.view_model);
            });

            var makeCycle = function () {
                this.location_types[0].parent_type = data.block.pk; // state.parent_type = block
                this.state_model.parent_type(this.block_model.pk);
                this.view_model = locationSettingsViewModel(this.location_types, false);

                this.state_model.view = this.view_model;
                this.district_model.view = this.view_model;
                this.block_model.view = this.view_model;
                this.supervisor_model.view = this.view_model;
            };

            describe('expand_from_options', function () {
                it('Provides all levels down to the current one, including root', function () {
                    var returnedLocTypes = _.map(
                            this.block_model.expand_from_options(),
                            extractName
                        ),
                        desiredLocTypesReturned = _.map([this.state_model, this.district_model], extractName);
                    desiredLocTypesReturned.push('root');
                    assert.sameMembers(desiredLocTypesReturned, returnedLocTypes);
                });

                it('Returns only root if there are cycles', function () {
                    makeCycle.call(this);
                    var returnedLocTypes = _.map(this.state_model.expand_from_options(), extractName);
                    assert(this.view_model.has_cycles());
                    assert.sameMembers(['root'], returnedLocTypes);
                });
            });

            describe('expand_to_options', function () {
                it('Provides all levels beneath the current one', function () {
                    var returnedLocTypes = _.map(this.district_model.expand_to_options().children, extractName),
                        desiredLocTypesReturned = _.map([this.district_model, this.block_model], extractName);
                    assert.isFalse(this.view_model.has_cycles());
                    assert.sameMembers(desiredLocTypesReturned, returnedLocTypes);
                });

                it('Returns the outermost leaf', function () {
                    var leaf = this.district_model.expand_to_options().leaf.name();
                    assert.equal(leaf, 'supervisor');
                });

                it('Returns empty if there are cycles', function () {
                    makeCycle.call(this);
                    var returnedLocTypes = _.map(this.state_model.expand_to_options().children, extractName);
                    assert(this.view_model.has_cycles());
                    assert.sameMembers([], returnedLocTypes);
                });

            });

            describe('include_without_expanding_options', function () {
                it('Provides all levels', function () {
                    var returnedLocTypes = _.map(
                            this.block_model.include_without_expanding_options(),
                            extractName
                        ),
                        desiredLocTypesReturned = _.map([this.state_model, this.district_model, this.block_model, this.supervisor_model], extractName);
                    assert.sameMembers(desiredLocTypesReturned, returnedLocTypes);
                });

                it('Provides nothing if expand from is root', function () {
                    this.block_model.expand_from(-1);
                    var returnedLocTypes = _.map(
                        this.block_model.include_without_expanding_options(),
                        extractName
                    );
                    assert.equal(0, returnedLocTypes.length);
                });
            });
        });

        describe('Forked Hierarchy', function () {
            var data = locationsData.forked;

            beforeEach(function () {
                this.location_types = _.map(data, function (data) {
                    return _.clone(data); // we mutate these values later
                });
                this.view_model = locationSettingsViewModel(this.location_types, false),
                this.state_model = locationTypeModel(data.state, false, this.view_model),
                this.county_model = locationTypeModel(data.county, false, this.view_model),
                this.city_model = locationTypeModel(data.city, false, this.view_model),
                this.region_model = locationTypeModel(data.region, false, this.view_model);
                this.town_model = locationTypeModel(data.town, false, this.view_model);
            });

            describe('expand_to_options', function () {
                it('shows when types are at the same level', function () {
                    var returnedLocTypes = this.state_model.expand_to_options(),
                        desiredChildrenReturned = ["state", "county | region"],
                        desiredLeafReturned = "city | town";

                    assert.isFalse(this.view_model.has_cycles());
                    assert.sameMembers(desiredChildrenReturned, _.map(
                        returnedLocTypes.children, extractName
                    ));
                    assert.equal(desiredLeafReturned, returnedLocTypes.leaf.name());
                });

                it('calculates the correct level', function () {
                    assert.equal(this.town_model.level(), 2);
                    assert.equal(this.state_model.level(), 0);
                    assert.equal(this.city_model.level(), 2);
                });

                it('shows correct levels when expand_from is above current fork', function () {
                    this.city_model.expand_from(this.state_model.pk);
                    var returnedLocTypes = this.city_model.expand_to_options(),
                        desiredChildrenReturned = ["state", "county | region"],
                        desiredLeafReturned = "city | town";
                    assert.sameMembers(desiredChildrenReturned, _.map(
                        returnedLocTypes.children, extractName
                    ));
                    assert.equal(desiredLeafReturned, returnedLocTypes.leaf.name());
                });

                it('shows all levels when expand_from is root', function () {
                    this.city_model.expand_from(-1);
                    var returnedLocTypes = this.city_model.expand_to_options(),
                        desiredChildrenReturned = ['state', 'county | region'],
                        desiredLeafReturned = "city | town";
                    assert.sameMembers(desiredChildrenReturned, _.map(
                        returnedLocTypes.children, extractName
                    ));
                    assert.equal(desiredLeafReturned, returnedLocTypes.leaf.name());
                });
            });

            describe('include_without_expanding_options', function () {
                it('Provides all levels', function () {
                    var returnedLocTypes = _.map(
                            this.region_model.include_without_expanding_options(),
                            extractName
                        ),
                        desiredLocTypesReturned = ['state', 'county | region', 'city | town'];
                    assert.sameMembers(desiredLocTypesReturned, returnedLocTypes);
                });
            });
        });
    });
});
