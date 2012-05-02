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
        var districts = [];
        self.enable_district(!!self.hsph_selected_region());
        if (self.enable_district())
            for (var dist in self.siteMap[self.hsph_selected_region()])
                districts.push(dist);
        self.hsph_districts(districts);
        self.updateDistrict();
    };

    self.updateDistrict = function () {
        var sites = [];
        self.enable_site(!!self.hsph_selected_district());
        if (self.enable_site()) {
            var sitesAvailable = self.siteMap[self.hsph_selected_region()][self.hsph_selected_district()];
            for (var site in sitesAvailable) {
                sites.push(new HSPHSite(site, sitesAvailable[site]));
            }
        }
        self.hsph_sites(sites);
    };

    self.updateRegion();
    self.updateDistrict();
};

var HSPHSite = function (id, name) {
    this.siteId = id;
    this.name = name;
};