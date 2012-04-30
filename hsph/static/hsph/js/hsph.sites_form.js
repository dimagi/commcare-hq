//ko.bindingHandlers.hsphRegionSelector = {
//    init: function(element, valueAccessor, allBindingsAccessora)
//}

var HSPHSitePicker = function (refs, currentSelection) {
    var self = this;
    self.siteMap = refs;
    var regions = [];
    for (var reg in self.siteMap)
        regions.push(reg);
    self.hsph_regions = ko.observableArray(regions);
    self.hsph_selected_region = ko.observable(currentSelection.region || "");

    self.hsph_districts = ko.observableArray();
    self.hsph_selected_district = ko.observable(currentSelection.district || "");
    self.enable_district = ko.observable(false);

    self.hsph_sites = ko.observableArray();
    self.enable_site = ko.observable(false);
    self.hsph_selected_site = ko.observable(currentSelection.siteNum || "");

    self.updateRegion = function () {
        console.log(self.hsph_selected_region());
        var districts = [];
        self.enable_district(!!self.hsph_selected_region());
        if (self.enable_district())
            for (var dist in self.siteMap[self.hsph_selected_region()])
                districts.push(dist);
        self.hsph_districts(districts);
    };

    self.updateDistrict = function () {
        console.log(self.hsph_selected_district());
        var sites = [];
        self.enable_site(!!self.hsph_selected_district());
        if (self.enable_site())
            for (var site in self.siteMap[self.hsph_selected_region()][self.hsph_selected_district()])
                sites.push(site);
        self.hsph_sites(sites);
    };

    self.updateRegion();
    self.updateDistrict();
};