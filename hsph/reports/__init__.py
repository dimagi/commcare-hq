from hsph.fields import SiteField

class HSPHSiteDataMixin(object):

    _site_map = None
    @property
    def site_map(self):
        if self._site_map is None:
            self._site_map = SiteField.getFacilities()
        return self._site_map

    _selected_site_map = None
    @property
    def selected_site_map(self):
        if self._selected_site_map is None:
            site_map = {}
            region = self.request.GET.get(SiteField.slugs['region'], None)
            district = self.request.GET.get(SiteField.slugs['district'], None)
            site = self.request.GET.get(SiteField.slugs['site'], None)
            if region:
                site_map[region] = dict(districts=self.site_map[region].get("districts", {}),
                    name=self.site_map[region].get("name", ""))
            if district:
                site_map[region]["districts"] = dict()
                site_map[region]["districts"][district] = dict(
                    sites=self.site_map[region]["districts"][district].get("sites", {}),
                    name=self.site_map[region]["districts"][district].get("name", "")
                )
                if site:
                    site_map[region]["districts"][district]["sites"] = dict()
                    site_map[region]["districts"][district]["sites"][site] = dict(
                        name=self.site_map[region]["districts"][district]["sites"][site].get("name", "")
                    )
            self._selected_site_map = site_map
        return self._selected_site_map

    def get_site_table_values(self, key):
        return self.get_region_name(key[0]),\
               self.get_district_name(key[0], key[1]),\
               self.get_site_name(key[0], key[1], key[2])

    def get_region_name(self, region):
        return self.site_map.get(region, {}).get("name", region)

    def get_district_name(self, region, district):
        return self.site_map.get(region, {}).get("districts", {}).get(district, {}).get("name", district)

    def get_site_name(self, region, district, site):
        return self.site_map.get(region, {}).get("districts", {}).get(district, {}).get("sites", {}).get(site, {}).get("name", site)

    def generate_keys(self, prefix=None, suffix=None):
        keys = [(prefix or [])+[region, district, site]+(suffix or [])
                for region, districts in self.selected_site_map.items()
                for district, sites in districts.get("districts",{}).items()
                for site, site_name in sites.get("sites",{}).items()]

        return keys
