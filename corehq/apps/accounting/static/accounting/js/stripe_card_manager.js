"use strict";
hqDefine("accounting/js/stripe_card_manager", [
    'jquery',
    'knockout',
    'accounting/js/stripe',
    'hqwebapp/js/initial_page_data',
], function (
    $,
    ko,
    hqStripe,
    initialPageData,
) {
    var newStripeCardModel = function (data, cardManager) {
        var self = {};

        // This assumes this model won't be created until the page is loaded,
        // which is reasonable because knockout bindings don't get applied until then.
        self.cardElementMounted = false;
        self.cardElementPromise = hqStripe.getCardElementPromise(initialPageData.get("stripe_public_key"));
        self.cardElementPromise.then(function (cardElement) {
            cardElement.mount(data.elementSelector);
            self.cardElementMounted = true;
        });

        var mapping = {
            observe: ['isAutopay', 'token'],
        };

        self.wrap = function (data) {
            ko.mapping.fromJS(data, mapping, self);
        };
        self.reset = function () {
            self.wrap({'isAutopay': false, 'token': ''});
            if (self.cardElementMounted) {
                self.cardElementPromise.then(function (cardElement) {
                    cardElement.clear();
                });
            }
        };
        self.reset();

        self.unwrap = function () {
            return {token: self.token(), autopay: self.isAutopay()};
        };

        self.isTestMode = ko.observable(false);
        self.isProcessing = ko.observable(false);
        self.errorMsg = ko.observable('');

        var submit = function () {
            // Sends the new card to HQ
            return $.ajax({
                type: "POST",
                url: data.url,
                data: self.unwrap(),
                success: function (data) {
                    $("#card-modal").modal('hide');
                    $("#success-modal").modal('show');
                    cardManager.wrap(data);
                    self.reset();
                },
            }).fail(function (data) {
                var response = JSON.parse(data.responseText);
                self.errorMsg(response.error);
            }).always(function () {
                self.isProcessing(false);
            });
        };

        var handleStripeResponse = function (response) {
            if (response.error) {
                self.isProcessing(false);
                self.errorMsg(response.error.message);
            } else {
                self.errorMsg('');
                self.token(response.token.id);
                submit();
            }
        };

        self.saveCard = function () {
            self.isProcessing(true);
            hqStripe.createStripeToken(handleStripeResponse);
        };

        return self;
    };

    var stripeCardModel = function (card, baseUrl, cardManager) {
        var self = {};
        var mapping = {
            include: ['brand', 'last4', 'exp_month','exp_year', 'is_autopay'],
            copy: ['url', 'token'],
        };

        self.wrap = function (data) {
            ko.mapping.fromJS(data, mapping, self);
            self.url = baseUrl + card.token + '/';
        };
        self.wrap(card);

        self.setAutopay = function () {
            cardManager.autoPayButtonEnabled(false);
            self.submit({is_autopay: true}).always(function () {
                cardManager.autoPayButtonEnabled(true);
            });
        };

        self.unSetAutopay = function () {
            cardManager.autoPayButtonEnabled(false);
            self.submit({is_autopay: false}).always(function () {
                cardManager.autoPayButtonEnabled(true);
            });
        };

        self.isDeleting = ko.observable(false);
        self.deleteErrorMsg = ko.observable('');
        self.deleteCard = function (card, button) {
            self.isDeleting(true);
            self.deleteErrorMsg = ko.observable('');
            cardManager.cards.destroy(card);
            $.ajax({
                type: "DELETE",
                url: self.url,
                success: function (data) {
                    cardManager.wrap(data);
                    $(button.currentTarget).closest(".modal").modal('hide');
                    $("#success-modal").modal('show');
                },
            }).fail(function (data) {
                var response = JSON.parse(data.responseText);
                self.deleteErrorMsg(response.error);
                if (response.cards) {
                    cardManager.wrap(response);
                }
            }).always(function () {
                self.isDeleting(false);
            });
        };

        self.submit = function (data) {
            return $.ajax({
                type: "POST",
                url: self.url,
                data: data,
                success: function (data) {
                    cardManager.wrap(data);
                },
            }).fail(function (data) {
                var response = JSON.parse(data.responseText);
                alert(response.error);
            });
        };

        return self;
    };


    var stripeCardManager = function (data) {
        var self = {};
        var mapping = {
            'cards': {
                create: function (card) {
                    return stripeCardModel(card.data, data.url, self);
                },
            },
        };

        self.wrap = function (data) {
            ko.mapping.fromJS(data, mapping, self);
        };
        self.wrap(data);

        self.autoPayButtonEnabled = ko.observable(true);
        self.newCard = newStripeCardModel({
            url: data.url,
            elementSelector: data.elementSelector,
        }, self);

        return self;
    };

    return {
        stripeCardManager: stripeCardManager,
    };
});
