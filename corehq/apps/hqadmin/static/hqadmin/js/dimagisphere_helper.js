var dimagisphere = (function() {
    var self = {};

    self.formData = {
        totalFormsByCountry: {},  // keeps track of totals per country
        recentFormsByCountry: {},  // keeps track of "active" per country - from the last second
        maxFormsByCountry: 0, // most forms that any single country has submitted
        totalFormsByDomain: {} // keeps track of totals per domain
    };

    self.addData = function (dataItem) {
        /**
         * Adds data to self.formData. Returns whether anything was done.
         */
        if (dataItem.country) {
            // update totals
            var currentCount = self.formData.totalFormsByCountry[dataItem.country] || 0;
            currentCount += 1;
            self.formData.totalFormsByCountry[dataItem.country] = currentCount;
            if (currentCount > self.formData.maxFormsByCountry) {
                self.formData.maxFormsByCountry = currentCount;
            }
            // update active
            var activeCount = self.formData.recentFormsByCountry[dataItem.country] || 0;
            self.formData.recentFormsByCountry[dataItem.country] = activeCount + 1;
            return true;
        }
        return false;
    };

    var FAKE_DOMAINS = {
        'dimagi': 'United States of America',
        'unicef': 'Nigeria',
        'mvp': 'Ethiopia',
        'dsi': 'India',
        'icds': 'India',
        'tula': 'Guatemala'
    };

    self.generateRandomItem = function () {
        // just return a random item from FAKE_DOMAINS
        // http://stackoverflow.com/questions/2532218/pick-random-property-from-a-javascript-object
        var domains = Object.keys(FAKE_DOMAINS);
        var randomDomain = domains[domains.length * Math.random() << 0];
        return {
            domain: randomDomain,
            country: FAKE_DOMAINS[randomDomain]
        };
    };
    return self;
})();
