import ko from "knockout";

const subdomainRegex = /(?<=:\/\/).*(?=\.commcarehq\.org)/;
const subdomainMatch = function (url) {
    return url.match(subdomainRegex);
};

const currentSubdomain = function (url) {
    const match = subdomainMatch(url);
    return match ? match[0] : "";
};

const replaceSubdomain = function (value, url) {
    return url.replace(subdomainRegex, value);
};

const serverLocationSelect = function (options) {
    const self = {};
    const url = options.url || window.location.href;
    const initialValue = options.initialValue || currentSubdomain(url);

    self.navigateTo = function (newUrl) {
        window.location.href = newUrl;
    };

    self.serverLocation = ko.observable(initialValue);
    self.serverLocation.subscribe(function (value) {
        if (subdomainMatch(url)) {
            const newUrl = replaceSubdomain(value, url);
            self.navigateTo(newUrl);
        }
    });
    return self;
};

export default serverLocationSelect;
