/*eslint-env mocha */
/*global _ LocationSelectViewModel */


/*eslint no-unused-vars:0*/
var LOAD_LOCS_URL = '/locations/api/';

describe('Location Drilldown', function() {
    var hierarchy = [["state", [null]], ["district", ["state"]], ["block", ["district"]]];

    it('should contain root object', function() {
        var viewModel = new LocationSelectViewModel({hierarchy: hierarchy});
        viewModel.load([], null);
        assert.equal(viewModel.root().name(), '_root');
    });

    it('should select given location when auto drill is enabled', function() {
        var viewModel = new LocationSelectViewModel({hierarchy: hierarchy});
        viewModel.load([{"can_edit": true, "uuid": "9e0e9e654660c8721ec07928971fa688", "name": "test", "is_archived": false, "location_type": "state"}], null);
        assert.equal(viewModel.selected_locid(), '9e0e9e654660c8721ec07928971fa688');
    });

    it('should not select given location when auto drill is disabled', function() {
        var viewModel = new LocationSelectViewModel({hierarchy: hierarchy, auto_drill: false});
        viewModel.load([{"can_edit": true, "uuid": "9e0e9e654660c8721ec07928971fa688", "name": "test", "is_archived": false, "location_type": "state"}], null);
        assert.isNull(viewModel.selected_locid());
    });
});
