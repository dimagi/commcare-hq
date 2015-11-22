var dimagisphere = (function() {
    var fn = {};
    var DOMAINS = {
        'dimagi': 'United States of America',
        'unicef': 'Nigeria',
        'mvp': 'Ethiopia',
        'dsi': 'India',
        'icds': 'India',
        'tula': 'Guatemala'
    };

    fn.generateRandomItem = function () {
        // just return a random item from DOMAINS
        // http://stackoverflow.com/questions/2532218/pick-random-property-from-a-javascript-object
        var domains = Object.keys(DOMAINS);
        var randomDomain = domains[domains.length * Math.random() << 0];
        return {
            domain: randomDomain,
            country: DOMAINS[randomDomain]
        }
    };
    return fn;
})();
