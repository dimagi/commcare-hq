/**
 * todo add docstring
 */

import _ from "underscore";
import assertProperties from "hqwebapp/js/assert_properties";
import initialPageData from "hqwebapp/js/initial_page_data";

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

    _.each(initialPageData.get('report.endpoints'), function (data) {
        self.endpoint[data.slug] = endpoint(data);
    });

    return self;
};

export default {
    getReportConfig: function () {
        return reportConfig();
    },
    getColumns: function () {
        return initialPageData.get('report.columns');
    },
    getUnsortableColumnNames: function () {
        return initialPageData.get('report.unsortableColumnNames');
    },
    getColumnFilters: function () {
        return initialPageData.get('report.columnFilters');
    },
    getReportFilters: function () {
        var filterData = initialPageData.get('report.reportFilters'),
            initialData = initialPageData.get('report.initialReportFilters'),
            config = reportConfig();
        filterData = _.map(filterData, function (data) {
            data.value = initialData[data.name];
            data.endpoint = config.endpoint[data.endpointSlug];
            return data;
        });
        return filterData;
    },
};
