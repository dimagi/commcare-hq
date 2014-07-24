function CustomField (field) {
    var self = this;
    self.name = ko.observable(field.name);
    self.isRequired = ko.observable(field.isRequired);
}


var CustomFieldsModel = function () {
    var self = this;
    self.customFields = ko.observableArray([]);

    self.addField = function () {
        self.customFields.push(new CustomField('', false));
    }

    self.init = function (initialFields) {
        _.each(initialFields, function (field) {
            console.log(field.name);
            self.customFields.push(new CustomField(field));
        });
    }

    // self.available_versions = ['{{ all_versions|join:"', '" }}'];
    // self.versions = ko.observableArray([])
    // self.available_ones = [];
    // self.available_twos = [];
    // self.default_one = ko.observable();
    // self.default_two = ko.observable();

    // self.addVersion = function() {
        // self.versions.push(new Version('', '', false));
    // }
    // self.removeVersion = function(version) { self.versions.remove(version) }

    // _.each(doc.menu, function(version) {
        // self.versions.push(new Version(
            // version.build.version, version.label, version.superuser_only
        // ));
    // });
    // _.each(doc.defaults, function(version_doc) {
        // var version = version_doc.version;
        // if (version[0] === '1') {
            // self.default_one(version);
        // } else if (version[0] === '2') {
            // self.default_two(version);
        // }
    // });
    // _.each(self.available_versions, function(version) {
        // if (version[0] === '1') {
            // self.available_ones.push(version);
        // } else if (version[0] === '2') {
            // self.available_twos.push(version);
        // }
    // });
}
