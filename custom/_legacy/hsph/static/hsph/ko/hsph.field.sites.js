var HSPHSitePicker = function (refs, currentSelection) {
    var self = this;
    self.siteMap = refs;
    var regions = [];
    for (var reg in self.siteMap)
        regions.push(new HSPHSiteItem(reg, self.siteMap[reg].name));

    self.regions = ko.observableArray(regions);
    self.selected_region = ko.observable(currentSelection.region || "");

    self.districts = ko.observableArray();
    self.selected_district = ko.observable(currentSelection.district || "");
    self.enable_district = ko.observable(false);

    self.sites = ko.observableArray();
    self.enable_site = ko.observable(false);
    self.selected_site = ko.observable(currentSelection.siteNum || "");

    self.updateRegion = function () {
        var districts = [];
        self.enable_district(!!self.selected_region());
        if (self.enable_district()) {
            var availableDistricts = self.siteMap[self.selected_region()].districts;
            for (var dist in availableDistricts)
                districts.push(new HSPHSiteItem(dist, availableDistricts[dist].name));
        }
        self.districts(districts);
        self.updateDistrict();
    };

    self.updateDistrict = function () {
        var sites = [];
        self.enable_site(!!self.selected_district());
        if (self.enable_site()) {
            var availableSites = self.siteMap[self.selected_region()].districts[self.selected_district()].sites;
            for (var site in availableSites) {
                sites.push(new HSPHSiteItem(site, availableSites[site].name));
            }
        }
        self.sites(sites);
    };

    self.updateRegion();
    self.updateDistrict();
};

var HSPHSiteItem = function (id, name) {
    this.item_id = id;
    this.name = name;
};