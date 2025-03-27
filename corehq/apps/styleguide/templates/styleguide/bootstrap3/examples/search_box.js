$(function () {
  var searchBoxExample = function () {
    var self = {};

    self.allItems = "alpha beta delta gamma epsilon omega chi".split(" ");
    self.items = ko.observableArray(self.allItems);

    self.query = ko.observable('');
    self.search = function (page) {
      self.items(_.filter(self.allItems, function (item) { return item.indexOf(self.query()) !== -1; }));
    };

    return self;
  };

  $("#search-box-example").koApplyBindings(searchBoxExample());
});
