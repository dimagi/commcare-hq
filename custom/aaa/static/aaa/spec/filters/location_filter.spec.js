/* global sinon */

describe('Reach Location Filter', function () {
    var locationFilter, locationModel, reachUtils, localStorage, pageData;

    beforeEach(function () {
        pageData = hqImport('hqwebapp/js/initial_page_data');
        locationFilter = hqImport('aaa/js/filters/location_filter');
        locationModel = hqImport('aaa/js/filters/location_model');
        reachUtils = hqImport('aaa/js/utils/reach_utils');
        pageData.registerUrl('location_api', 'location_api');
        localStorage = reachUtils.localStorage();
    });

    it('test template', function () {
        assert.equal(locationFilter.template, '<div data-bind="template: { name: \'location-template\' }"></div>');
    });

    describe('when user is not assigned to location', function () {
        var mock;

        beforeEach(function () {
            mock = sinon.stub(pageData, 'get');
            mock.withArgs('user_role_type').returns(reachUtils.USERROLETYPES.MWCD);
            mock.withArgs('user_location_ids').returns([]);
            mock.withArgs('selected_location_ids').returns([]);
        });

        afterEach(function () {
            mock.restore();
        });

        it('test filter initialization', function () {
            var model = locationFilter.viewModel({
                filters: {'location-filter': {}},
                localStorage: localStorage,
            });
            assert.equal(model.userRoleType, reachUtils.USERROLETYPES.MWCD);
            assert.deepEqual(model.userLocationIds, []);
            var state = locationModel.locationModel({slug: 'state', name: 'State', parent: '', userLocationId: void(0), postData: {}});
            var district = locationModel.locationModel({slug: 'district', name: 'District', parent: state, userLocationId: void(0), postData: {}});
            state.setChild(district);
            var block = locationModel.locationModel({slug: 'block', name: 'Block', parent: district, userLocationId: void(0), postData: {}});
            district.setChild(block);
            var supervisor = locationModel.locationModel({slug: 'supervisor', name: 'Sector (Project)', parent: block, userLocationId: void(0), postData: {}});
            block.setChild(supervisor);
            var awc = locationModel.locationModel({slug: 'awc', name: 'AWC', parent: supervisor, userLocationId: void(0), postData: {}});
            supervisor.setChild(awc);
            var expectedHierarchy = [
                state,
                district,
                block,
                supervisor,
                awc,
            ];
            _.each(expectedHierarchy, function (element, idx) {
                assert.equal(model.hierarchyConfig()[idx].slug, element.slug);
                assert.equal(model.hierarchyConfig()[idx].name, element.name);
                assert.equal(model.hierarchyConfig()[idx].userLocationId, element.userLocationId);
                if (element.parent !== '') {
                    assert.equal(model.hierarchyConfig()[idx].parent.slug, element.parent.slug);
                    assert.equal(model.hierarchyConfig()[idx].parent.name, element.parent.name);
                }
                if (element.child !== null) {
                    assert.equal(model.hierarchyConfig()[idx].child.slug, element.child.slug);
                    assert.equal(model.hierarchyConfig()[idx].child.name, element.child.name);
                }
            });
        });
    });

    describe('when user is assigned to location', function () {
        var mock;

        beforeEach(function () {
            mock = sinon.stub(pageData, 'get');
            mock.withArgs('user_role_type').returns(reachUtils.USERROLETYPES.MOHFW);
            mock.withArgs('user_location_ids').returns(['s1', 'd1', 't1']);
            mock.withArgs('selected_location_ids').returns([]);
        });

        afterEach(function () {
            mock.restore();
        });

        it('test filter initialization', function () {
            var model = locationFilter.viewModel({
                filters: {'location-filter': {}},
                localStorage: localStorage,
            });
            assert.equal(model.userRoleType, reachUtils.USERROLETYPES.MOHFW);
            assert.deepEqual(model.userLocationIds, ['s1', 'd1', 't1']);
            var state = locationModel.locationModel({slug: 'state', name: 'State', parent: '', userLocationId: 's1', postData: {}});
            var district = locationModel.locationModel({slug: 'district', name: 'District', parent: state, userLocationId: 'd1', postData: {}});
            state.setChild(district);
            var taluka = locationModel.locationModel({slug: 'taluka', name: 'Taluka', parent: district, userLocationId: 't1', postData: {}});
            district.setChild(taluka);
            var phc = locationModel.locationModel({slug: 'phc', name: 'Primary Health Centre (PHC)', parent: taluka, userLocationId: void(0), postData: {}});
            taluka.setChild(phc);
            var sc = locationModel.locationModel({slug: 'sc', name: 'Sub-centre (SC)', parent: phc, userLocationId: void(0), postData: {}});
            phc.setChild(sc);
            var village = locationModel.locationModel({slug: 'village', name: 'Village', parent: sc, userLocationId: void(0), postData: {}});
            sc.setChild(village);
            var expectedHierarchy = [
                state,
                district,
                taluka,
                phc,
                sc,
                village,
            ];
            _.each(expectedHierarchy, function (element, idx) {
                assert.equal(model.hierarchyConfig()[idx].slug, element.slug);
                assert.equal(model.hierarchyConfig()[idx].name, element.name);
                assert.equal(model.hierarchyConfig()[idx].userLocationId, element.userLocationId);
                if (element.parent !== '') {
                    assert.equal(model.hierarchyConfig()[idx].parent.slug, element.parent.slug);
                    assert.equal(model.hierarchyConfig()[idx].parent.name, element.parent.name);
                }
                if (element.child !== null) {
                    assert.equal(model.hierarchyConfig()[idx].child.slug, element.child.slug);
                    assert.equal(model.hierarchyConfig()[idx].child.name, element.child.name);
                }
            });
        });
    });

    describe('when selectedLocation is a url parameter', function () {
        var mock;

        beforeEach(function () {
            mock = sinon.stub(pageData, 'get');
            mock.withArgs('user_role_type').returns(reachUtils.USERROLETYPES.MOHFW);
            mock.withArgs('user_location_ids').returns([]);
            mock.withArgs('selected_location_ids').returns(['s1', 'd1', 't1']);
        });

        afterEach(function () {
            mock.restore();
        });

        it('test filter initialization', function () {
            var model = locationFilter.viewModel({
                filters: {'location-filter': {}},
                localStorage: localStorage,
            });
            assert.equal(model.userRoleType, reachUtils.USERROLETYPES.MOHFW);
            assert.deepEqual(model.selectedLocationIds, ['s1', 'd1', 't1']);
            var state = locationModel.locationModel({slug: 'state', name: 'State', parent: '', userLocationId: 's1', postData: {}});
            var district = locationModel.locationModel({slug: 'district', name: 'District', parent: state, userLocationId: 'd1', postData: {}});
            state.setChild(district);
            var taluka = locationModel.locationModel({slug: 'taluka', name: 'Taluka', parent: district, userLocationId: 't1', postData: {}});
            district.setChild(taluka);
            var phc = locationModel.locationModel({slug: 'phc', name: 'Primary Health Centre (PHC)', parent: taluka, userLocationId: void(0), postData: {}});
            taluka.setChild(phc);
            var sc = locationModel.locationModel({slug: 'sc', name: 'Sub-centre (SC)', parent: phc, userLocationId: void(0), postData: {}});
            phc.setChild(sc);
            var village = locationModel.locationModel({slug: 'village', name: 'Village', parent: sc, userLocationId: void(0), postData: {}});
            sc.setChild(village);
            var expectedHierarchy = [
                state,
                district,
                taluka,
                phc,
                sc,
                village,
            ];
            _.each(expectedHierarchy, function (element, idx) {
                assert.equal(model.hierarchyConfig()[idx].slug, element.slug);
                assert.equal(model.hierarchyConfig()[idx].name, element.name);
                if (element.parent !== '') {
                    assert.equal(model.hierarchyConfig()[idx].parent.slug, element.parent.slug);
                    assert.equal(model.hierarchyConfig()[idx].parent.name, element.parent.name);
                }
                if (element.child !== null) {
                    assert.equal(model.hierarchyConfig()[idx].child.slug, element.child.slug);
                    assert.equal(model.hierarchyConfig()[idx].child.name, element.child.name);
                }
            });
        });
    });

    describe('location model', function () {
        it('test model initialization', function () {
            var model = locationModel.locationModel({slug: 'state', name: 'State', parent: '', userLocationId: void(0), postData: {}});
            assert.equal(model.slug, 'state');
            assert.equal(model.name, 'State');
            assert.equal(model.parent, '');
            assert.equal(model.child, null);
            assert.equal(model.userLocationId, void(0));
            assert.deepEqual(model.locations(), [reachUtils.DEFAULTLOCATION]);
            assert.equal(model.selectedLocation(), reachUtils.DEFAULTLOCATION.id);
        });

        it('test model initialization with parent', function () {
            var parent = locationModel.locationModel({slug: 'state', name: 'State', parent: '', userLocationId: void(0), postData: {}});
            var model = locationModel.locationModel({slug: 'block', name: 'Block', parent: parent, userLocationId: void(0), postData: {}});
            assert.equal(model.slug, 'block');
            assert.equal(model.name, 'Block');
            assert.equal(model.parent.slug, 'state');
            assert.equal(model.parent.name, 'State');
            assert.equal(model.child, null);
            assert.equal(model.userLocationId, void(0));
            assert.deepEqual(model.locations(), [reachUtils.DEFAULTLOCATION]);
            assert.equal(model.selectedLocation(), reachUtils.DEFAULTLOCATION.id);
        });

        it('test model initialization with child', function () {
            var model = locationModel.locationModel({slug: 'state', name: 'State', parent: '', userLocationId: void(0), postData: {}});
            var child = locationModel.locationModel({slug: 'block', name: 'Block', parent: model, userLocationId: void(0), postData: {}});
            model.setChild(child);
            assert.equal(model.slug, 'state');
            assert.equal(model.name, 'State');
            assert.equal(model.child.slug, 'block');
            assert.equal(model.child.name, 'Block');
            assert.equal(model.userLocationId, void(0));
            assert.deepEqual(model.locations(), [reachUtils.DEFAULTLOCATION]);
            assert.equal(model.selectedLocation(), reachUtils.DEFAULTLOCATION.id);
        });



        it('test model initialization when user is assign to location', function () {
            var model = locationModel.locationModel({slug: 'state', name: 'State', parent: '', userLocationId: 's1', postData: {}});
            var child = locationModel.locationModel({slug: 'block', name: 'Block', parent: model, userLocationId: void(0), postData: {}});
            model.setChild(child);
            var testLocations = {
                data: [
                    {id: 'all', name: 'All'},
                    {id: 's1', name: 'S1'},
                    {id: 's2', name: 'S2'},
                ],
            };
            model.setData(testLocations);
            assert.equal(model.slug, 'state');
            assert.equal(model.name, 'State');
            assert.equal(model.userLocationId, 's1');
            assert.equal(model.selectedLocation(), 's1');
        });

        it('test update child when selected location in parent will be changed', function () {
            var model = locationModel.locationModel({slug: 'state', name: 'State', parent: '', userLocationId: 's1', postData: {}});
            var child = locationModel.locationModel({slug: 'block', name: 'Block', parent: model, userLocationId: 'b1', postData: {}});
            model.setChild(child);
            var testParentLocations = {
                data: [
                    {id: 's1', name: 'S1'},
                    {id: 's2', name: 'S2'},
                ],
            };
            var testChildLocations = {
                data: [
                    {id: 'all', name: 'All'},
                    {id: 'b1', name: 'B1'},
                    {id: 'b2', name: 'b2'},
                ],
            };
            model.setData(testParentLocations);
            child.setData(testChildLocations);
            assert.equal(model.userLocationId, 's1');
            assert.equal(model.selectedLocation(), 's1');
            assert.equal(child.userLocationId, 'b1');
            assert.equal(child.selectedLocation(), 'b1');

            model.selectedLocation('s2');

            assert.equal(model.userLocationId, 's1');
            assert.equal(model.selectedLocation(), 's2');
            assert.equal(child.userLocationId, 'b1');
            assert.equal(child.selectedLocation(), 'all');
        });
    });
});
