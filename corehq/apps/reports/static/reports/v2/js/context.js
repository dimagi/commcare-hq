/**
 * todo add docstring
 */

hqDefine('reports/v2/js/context', [
    'jquery',
    'knockout',
    'underscore',
    'hqwebapp/js/assert_properties',
    'hqwebapp/js/initial_page_data',
], function (
    $,
    ko,
    _,
    assertProperties,
    initialPageData
) {
    'use strict';

    var endpoint = function (data) {
        assertProperties.assert(data, ['slug', 'urlname']);

        var self = {};

        self.slug = data.slug;
        self.urlname = data.urlname;

        self.getUrl = function () {
            return initialPageData.reverse(self.urlname, self.slug);
        };

        return self;
    };

    var reportConfig = function () {
        var self = {};

        self.endpoint = {};

        self.init = function () {

            _.each(initialPageData.get('report.endpoints'), function (data) {
                self.endpoint[data.slug] = endpoint(data);
            });

        };

        return self;
    };

    return {
        getReportConfig: function () {
            return new reportConfig();
        },
    };
});
