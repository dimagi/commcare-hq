from hsph.fields import SiteField

class HSPHSiteDataMixin:
    request = None

    def generate_sitemap(self):
        self.site_map = SiteField.getFacilities()
        self.selected_site_map = {}

        region = self.request.GET.get(SiteField.slugs['region'], None)
        district = self.request.GET.get(SiteField.slugs['district'], None)
        site = self.request.GET.get(SiteField.slugs['site'], None)

        if region:
            self.selected_site_map[region] = dict(districts=self.site_map[region].get("districts", {}),
                name=self.site_map[region].get("name", ""))
            if district:
                self.selected_site_map[region]["districts"] = dict()
                self.selected_site_map[region]["districts"][district] = dict(sites=self.site_map[region]["districts"][district].get("sites", {}),
                    name=self.site_map[region]["districts"][district].get("name", ""))
                if site:
                    self.selected_site_map[region]["districts"][district]["sites"] = dict()
                    self.selected_site_map[region]["districts"][district]["sites"][site] = dict(name=self.site_map[region]["districts"][district]["sites"][site].get("name", ""))

    def get_site_table_values(self, key):
        return self.get_region_name(key[0]), \
               self.get_district_name(key[0], key[1]), \
               self.get_site_name(key[0], key[1], key[2])

    def get_region_name(self, region):
        return self.site_map.get(region, {}).get("name", region)

    def get_district_name(self, region, district):
        return self.site_map.get(region, {}).get("districts", {}).get(district, {}).get("name", district)

    def get_site_name(self, region, district, site):
        return self.site_map.get(region, {}).get("districts", {}).get(district, {}).get("sites", {}).get(site, {}).get("name", site)

    def generate_keys(self, prefix=[], suffix=[]):
        keys = [prefix+[region, district, site]+suffix
                for region, districts in self.selected_site_map.items()
                    for district, sites in districts.get("districts",{}).items()
                        for site, site_name in sites.get("sites",{}).items()]

        return keys