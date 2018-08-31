/**
 * todo add docstring
 */

hqDefine('reports/v2/js/context', [
  'jquery',
  'knockout',
  'underscore',  // can we switch to lodash?
  'hqwebapp/js/initial_page_data',
], function (
    $,
    ko,
    _,
    initialPageData
) {
  'use strict';

  var Endpoint = function (data) {
    var self = this;

    self.slug = data.slug;
    self.urlname = data.urlname;

    self.getUrl = function () {
      return initialPageData
              .reverse(self.urlname)
              .replace('slug', self.slug);
    };

  };

  var ReportConfig = function () {
    var self = this;

    self.endpoint = {};

    self.init = function() {

      _.each(initialPageData.get('report.endpoints'), function (data) {
        console.log(data);
        self.endpoint[data.slug] = new Endpoint(data);
      });

    };
  };

  return {
    getReportConfig: function () {
      return new ReportConfig();
    }
  };
});
