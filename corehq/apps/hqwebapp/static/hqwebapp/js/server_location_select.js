import ko from "knockout";

const subdomainRegex = /(?<=:\/\/).*(?=\.commcarehq\.org)/;
const subdomainMatch = function () {
    return window.location.href.match(subdomainRegex);
};

const currentSubdomain = function () {
    const match = subdomainMatch();
    return match ? match[0] : "";
};

const navigateSubdomain = value => {
    const match = subdomainMatch();
    if (match) {
        window.location.href = window.location.href.replace(subdomainRegex, value);
    }
};

const serverLocationModel = function (initialValue = currentSubdomain()) {
    const self = {};
    self.serverLocation = ko.observable(initialValue);
    self.serverLocation.subscribe(value => navigateSubdomain(value));
    return self;
};

export default {
    serverLocationModel: serverLocationModel,
};
