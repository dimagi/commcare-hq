/*eslint-env mocha */


describe('Location Drilldown', function() {
    var hierarchy = [["state", [null]], ["district", ["state"]], ["block", ["district"]]];
    var locationSelectViewModel = hqImport('locations/js/location_drilldown').locationSelectViewModel;

    it('should contain root object', function() {
        var viewModel = new locationSelectViewModel({hierarchy: hierarchy});
        viewModel.load([], null);
        assert.equal(viewModel.root().name(), '_root');
    });

    it('should select given location when auto drill is enabled', function() {
        var viewModel = new locationSelectViewModel({hierarchy: hierarchy});
        var locations = [
            {
                "can_edit": true,
                "uuid": "state_1",
                "name": "test",
                "is_archived": false,
                "location_type": "state",
                "have_access_to_parent": true,
                "children": [
                    {
                        "can_edit": true,
                        "uuid": "district_1",
                        "name": "test",
                        "is_archived": false,
                        "location_type": "district",
                        "have_access_to_parent": true,
                        "children": [
                            {
                                "can_edit": true,
                                "uuid": "block_1",
                                "name": "test",
                                "is_archived": false,
                                "have_access_to_parent": true,
                                "location_type": "block",
                            },
                        ],
                    },
                ],
            },
        ];
        viewModel.load(locations, 'state_1');
        assert.equal(viewModel.selected_locid(), 'block_1');
    });

    it('should not select given location when auto drill is disabled', function() {
        var viewModel = new locationSelectViewModel({hierarchy: hierarchy, auto_drill: false});
        var locations = [
            {
                "can_edit": true,
                "uuid": "state_1",
                "name": "test",
                "is_archived": false,
                "location_type": "state",
                "have_access_to_parent": true,
                "children": [
                    {
                        "can_edit": true,
                        "uuid": "district_1",
                        "name": "test",
                        "is_archived": false,
                        "location_type": "district",
                        "have_access_to_parent": true,
                        "children": [
                            {
                                "can_edit": true,
                                "uuid": "block_1",
                                "name": "test",
                                "is_archived": false,
                                "have_access_to_parent": true,
                                "location_type": "block",
                            },
                        ],
                    },
                ],
            },
        ];
        viewModel.load(locations, 'state_1');
        assert.equal(viewModel.selected_locid(), 'state_1');
    });
});
