var PricingTable = function (pricing_table, current_edition, isNonAccountingSuperuser) {
    'use strict';
    var self = this;

    self.currentEdition = current_edition;
    self.isNonAccountingSuperuser = isNonAccountingSuperuser;
    self.title = ko.observable(pricing_table.title);
    self.editions = ko.observableArray(_.map(pricing_table.editions, function (edition) {
        return new PricingTableEdition(edition, self.currentEdition);
    }));
    self.sections = ko.observableArray(_.map(pricing_table.sections, function (section) {
        return new PricingTableSection(section);
    }));
    self.footer = ko.observableArray(pricing_table.footer);

    self.table_colspan = ko.computed(function () {
        return self.editions().length + 2;
    });

    self.visit_wiki_text = ko.observable(pricing_table.visit_wiki_text);

    self.selected_edition = ko.observable();
    self.isEditionSelectable = ko.computed(function () {
        return !self.isNonAccountingSuperuser || ['community', 'enterprise'].indexOf(self.selected_edition()) >= 0;
    });
    self.isSubmitVisible = ko.computed(function () {
        return !! self.selected_edition() && !(self.selected_edition() === self.currentEdition) && self.isEditionSelectable();
    });
    self.isSuperuserNoticeVisible = ko.computed(function () {
        return !(self.selected_edition() === self.currentEdition) && !self.isEditionSelectable() && !! self.selected_edition();
    });

    self.init = function () {
        $('.edition-heading').tooltip();
        $('.col-edition').click(function () {
            self.selected_edition($(this).data('edition'));
        });
    };
};

var PricingTableEdition = function (data, current_edition) {
    'use strict';
    var self = this;

    self.slug = ko.observable(data[0]);
    self.name = ko.observable(data[1].name);
    self.description = ko.observable(data[1].description);
    self.currentEdition = ko.observable(data[0] === current_edition);
    self.notCurrentEdition = ko.computed(function (){
        return !self.currentEdition();
    });
    self.col_css = ko.computed(function () {
       return 'col-edition col-edition-' + self.slug();
    });
};

var PricingTableSection = function (section) {
    'use strict';
    var self = this;

    self.show_header = ko.observable(section.category !== 'core');
    self.edition = ko.observable(section.edition);

    self.title = ko.observable(section.title);
    self.url = ko.observable(section.url);
    self.features = ko.observableArray(_.map(section.features, function (feature) {
        return new PricingTableFeature(feature);
    }));

    self.tbody_css = ko.computed(function () {
        return (self.show_header()) ? 'tbody-feature-details' : '';
    });
};

var PricingTableFeature = function (feature) {
    'use strict';
    var self = this;

    self.title = ko.observable(feature.title);
    self.columns = ko.observableArray(_.map(feature.columns, function (column) {
        return new PricingTableColumn(column);
    }));
};

var PricingTableColumn = function (data) {
    'use strict';
    var self = this;

    self.edition = ko.observable(data[0]);
    self.content = ko.observable(data[1]);

    self.content_html = ko.computed(function () {
        if (_.isBoolean(self.content())) {
            var icon_class = (self.content()) ? 'icon-ok' : 'icon-minus';
            return '<i class="' + icon_class + '"></i>';
        }
        return self.content();
    });

    self.col_css = ko.computed(function () {
        return 'col-edition col-edition-' + self.edition();
    });

};


