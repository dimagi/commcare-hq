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
            self.selected_site_map[region] = self.site_map[region]
            if district:
                self.selected_site_map[region] = {}
                self.selected_site_map[region][district] = self.site_map[region][district]
                if site:
                    self.selected_site_map[region][district] = {}
                    self.selected_site_map[region][district][site] = self.site_map[region][district][site]

    def get_site_table_values(self, key):
        region = key[0]
        district = key[1]
        site_num = key[2]
        site_name = self.site_map.get(region, {}).get(district, {}).get(site_num)
        return region, district, site_num, site_name

    def generate_keys(self, prefix=[]):
        keys = [prefix+[region, district, site]
                for region, districts in self.selected_site_map.items()
                        for district, sites in districts.items()
                            for site in sites]

        return keys