angular.module('icdsApp').directive("filters", function() {
    var url = hqImport('hqwebapp/js/urllib.js').reverse;
    return {
        restrict:'E',
        scope: {
            data: '='
        },
        bindToController: true,
        templateUrl: url('icds-ng-template', 'filters'),
        controller: function() {},
        controllerAs: "$ctrl"
    }
});

angular.module('icdsApp').directive("locationFilter", function() {
    var url = hqImport('hqwebapp/js/urllib.js').reverse;
    return {
        restrict:'E',
        scope: {
            location: '='
        },
        bindToController: true,
        require: 'ngModel',
        templateUrl: url('icds-ng-template', 'location_filter'),
        controller: function LocationFilterControler() {
          this.locations = [
              {name: 'Location 1'},
              {name: 'Location 2'},
              {name: 'Location 3'},
              {name: 'Location 4'},
              {name: 'Location 5'}
          ];
        },
        controllerAs: "$locationCtrl"
    }
});

angular.module('icdsApp').filter('propsFilter', function() {
  return function(items, props) {
    var out = [];

    if (angular.isArray(items)) {
      var keys = Object.keys(props);

      items.forEach(function(item) {
        var itemMatches = false;

        for (var i = 0; i < keys.length; i++) {
          var prop = keys[i];
          var text = props[prop].toLowerCase();
          if (item[prop].toString().toLowerCase().indexOf(text) !== -1) {
            itemMatches = true;
            break;
          }
        }

        if (itemMatches) {
          out.push(item);
        }
      });
    } else {
      // Let the output be the input untouched
      out = items;
    }

    return out;
  };
});