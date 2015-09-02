var NewStripeCard = function(data){
    'use strict';
    var self = this;
    var mapping = {
        observe: ['number', 'cvc', 'expMonth','expYear', 'isAutopay', 'token']
    };

    self.wrap = function(data){
        ko.mapping.fromJS(data, mapping, self);
    };
    self.wrap({'number': '', 'cvc': '', 'expMonth': '', 'expYear': '', 'isAutopay': false, 'token': ''});

    self.isTestMode = ko.observable(false);
    self.isProcessing = ko.observable(false);
    self.agreedToPrivacyPolicy = ko.observable(false);

    self.save = function(){
        console.log(ko.mapping.toJS(self));
    };
};

var StripeCard = function(card){
    'use strict';
    var self = this;
    var mapping = {
        include: ['brand', 'last4', 'exp_month','exp_year', 'is_autopay'],
        copy: ['url', 'token']
    };

    self.wrap = function(data){
        ko.mapping.fromJS(data, mapping, self);
        self.is_autopay(self.is_autopay() == 'True');
    };
    self.wrap(card);

    self.setAutopay = function(){
        cardManager.autoPayButtonEnabled(false);
        self.submit({is_autopay: true}).always(function(){
            cardManager.autoPayButtonEnabled(true);
        });
    };

    self.unSetAutopay = function(){
        cardManager.autoPayButtonEnabled(false);
        self.submit({is_autopay: false}).always(function(){
            cardManager.autoPayButtonEnabled(true);
        });
    };

    self.showDeleteConfirmation = ko.observable(false);
    self.toggleDeleteConfirmation = function(){
        self.showDeleteConfirmation(!self.showDeleteConfirmation());
    };

    self.deleteCard = function(card){
        cardManager.cards.destroy(card);
        $.ajax({
            type: "DELETE",
            url: self.url
        }).success(function(data){
            cardManager.wrap(data);
        }).fail(function(data){
            var response = JSON.parse(data.responseText);
            alert_user(response.error, "error");
            if (response.cards){
                cardManager.wrap(response);
            }
        });
    };

    self.submit = function(data){
        return $.ajax({
            type: "POST",
            url: self.url,
            data: data
        }).success(function(data){
            cardManager.wrap(data);
        }).fail(function(){
            alert("something went horribly wrong");
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
    self.newCard = new NewStripeCard();
    console.log(self.newCard);
};
