/**
 * todo add docstring
 */

hqDefine('reports/v2/js/columns', [
  'lodash',  // can we switch to lodash?
  'reports/v2/js/formatters',
], function (
    _,
    Formatters
) {
  'use strict';

  var Column = function (data) {
    var self = this;
    self.title = data.title;
    self.slug = data.slug;
    self.format = data.format || 'default';

    self.getFormatter = function () {
      var formatterFn = Formatters[self.format];
      if (!formatterFn) {
        formatterFn = Formatters.default;
      }
      return formatterFn;
    };

    self.getOptions = function () {
      /**
       * Returns the options formatted as datatables expects them.
       * reference: https://datatables.net/reference/option/columns
       */
      return {
        title: self.title,
        data: self.slug,
        render: self.getFormatter(),
      };
    };
  };

  var ColumnFilter = function (data) {
    var self = this;

    self.columns = [];

    self.init = function () {

    }

  };

  return {
    getColumnFilter: function (data) {
      return data;
    }
  };
});
