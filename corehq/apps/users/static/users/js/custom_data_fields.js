/**
 *  This file defines a model for editing custom data fields while creating or editing a mobile user.
 */
hqDefine("users/js/custom_data_fields", [
    'knockout',
    'underscore',
    'hqwebapp/js/assert_properties',
], function (
    ko,
    _,
    assertProperties
) {
    var fieldModel = function (value) {
        return {
            value: ko.observable(value),
            previousValue: ko.observable(value),    // save user-entered value
            disable: ko.observable(false),
        };
    };

    var customDataFieldsEditor = function (options) {
        assertProperties.assertRequired(options, ['profiles', 'slugs', 'profile_slug']);
        var self = {};

        self.profiles = _.indexBy(options.profiles, 'id');
        self.profile_slug = options.profile_slug;
        self.slugs = options.slugs;
        _.each(self.slugs, function (slug) {
            self[slug] = fieldModel('');    // TODO: populate with original value, inc. for disabled
        });

        self.serialize = function () {
            var data = {};
            data[self.profile_slug] = self[self.profile_slug].value();
            _.each(self.slugs, function (slug) {
                data[slug] = self[slug].value();
            });
            return data;
        };

        self[self.profile_slug] = fieldModel('');   // TODO: populate with original value
        self[self.profile_slug].value.subscribe(function (newValue) {
            if (!newValue) {
                return;
            }
            var profile = self.profiles[newValue];
            _.each(self.slugs, function (slug) {
                var field = self[slug];
                if (slug in profile.fields) {
                    if (!field.disable()) {
                        field.previousValue(field.value());
                    }
                    field.value(profile.fields[slug]);
                    field.disable(true);
                } else {
                    if (field.disable()) {
                        field.value(field.previousValue());
                    }
                    field.disable(false);
                }
            });
        });

        return self;
    };

    return {
        customDataFieldsEditor: customDataFieldsEditor,
    };
});
