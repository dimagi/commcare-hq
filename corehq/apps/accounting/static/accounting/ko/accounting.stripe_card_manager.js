var StripeCard = function(card){
    'use strict';
    var self = this;
    var mapping = {
        include: ['brand', 'last4', 'exp_month','exp_year', 'is_autopay'],
        copy: ['url', 'token']
    };

    ko.mapping.fromJS(card, mapping, self);
    self.is_autopay(self.is_autopay() == 'True');

    self.setAutopay = function(){
        self.is_autopay(true);
        self.submit({is_autopay: self.is_autopay()});
    };

    self.unSetAutopay = function(){
        self.is_autopay(false);
        self.submit({is_autopay: self.is_autopay()});
    };

    self.submit = function(data){
        cardManager.autoPayButtonEnabled(false);
        $.ajax({
            type: "POST",
            url: self.url,
            data: data
        }).success(function(data){
            cardManager.wrap(data);
        }).always(function(){
            cardManager.autoPayButtonEnabled(true);
        });
    };
};


var StripeCardManager = function(data){
    'use strict';
    var self = this;
    var mapping = {
        'cards':{
            create: function(card){
                return new StripeCard(card.data);
            }
        }
    };

    self.wrap = function(data){
        ko.mapping.fromJS(data, mapping, self);
    };
    self.wrap(data);

    self.autoPayButtonEnabled = ko.observable(true);
};
