"use strict";
hqDefine('accounting/js/payment_method_handler', [
    'jquery',
    'knockout',
    'underscore',
    'accounting/js/lib/stripe',
], function (
    $,
    ko,
    _,
    Stripe
) {
    var billingHandler = function (formId, opts) {
        var self = {};
        self.CREDIT_CARD = 'cc';
        self.WIRE = 'wire';

        self.formId = formId;
        self.errorMessages = opts.errorMessages || {};
        self.submitBtnText = opts.submitBtnText;
        self.costItem = ko.observable();
        self.hasCostItem = ko.computed(function () {
            return !! self.costItem();
        });

        self.isWire = ko.observable(opts.isWire || false);
        self.wireEmails = ko.observable('');

        self.paymentIsComplete = ko.observable(false);
        self.paymentIsNotComplete = ko.computed(function () {
            return ! self.paymentIsComplete();
        });
        self.paymentIsComplete.subscribe(function (value) {
            if (value) {
                // Since there is no great way to connect this model with
                // the subscription summary info, use this hacky way to update
                // the total of the general amount so the user is
                // aware something happened.
                var $generalCredit = $('.js-general-credit');

                // make sure this only applies on pages where that class is present
                if ($generalCredit && self.costItem() && self.costItem().general_credit) {

                    var addedAmount = self.costItem().general_credit().addAmount(),
                        newValue = parseFloat($generalCredit.text().replace('USD ', '').trim()) + parseFloat(addedAmount);
                    $generalCredit.text('USD ' + newValue.toFixed(2));

                    // make sure we reset the credit amount to zero so that the next
                    // time the user opens the form (before a page refresh),
                    // the value isn't already set
                    self.costItem().general_credit().addAmount(0);
                }
            }
        });
        self.paymentProcessing = ko.observable(false);

        self.serverErrorMsg = ko.observable();
        self.showServerErrorMsg = ko.computed(function () {
            return !! self.serverErrorMsg();
        });
        self.submitURL = opts.submitURL;

        self.paymentMethod = ko.observable();

        self.submitForm = function () {
            $('#' + self.formId).ajaxSubmit({
                success: self.handleSuccess,
                error: self.handleGeneralError,
            });
        };
        return self;
    };

    var wireInvoiceHandler = function (formId, opts) {
        var self = {};
        opts = opts ? opts : {};

        self = billingHandler.apply(self, [formId, opts]);
        self.paymentMethod = ko.observable(self.WIRE);

        self.handleGeneralError = function (response, textStatus, errorThrown) {
            errorThrown = errorThrown || 500;
            self.serverErrorMsg(self.errorMessages[errorThrown]);
        };

        self.handleSuccess = function (response) {
            if (response.success) {
                self.costItem().reset();
                self.paymentIsComplete(true);
            }
        };

        self.isSubmitDisabled = ko.computed(function () {
            return !(self.costItem() && self.costItem().isValid());
        });
        self.processPayment = function () {
            self.submitForm();
        };
        self.hasAgreedToPrivacy = true; // No privacy policy for wire
        return self;
    };

    var paymentMethodHandler = function (formId, opts) {
        var self = {};
        opts = opts ? opts : {};

        self = billingHandler.apply(self, arguments);
        self.paymentMethod = ko.observable(self.CREDIT_CARD);

        self.submitURL = self.submitURL || ko.computed(function () {
            var url = opts.credit_card_url;
            if (self.paymentMethod() === self.WIRE) {
                url = opts.wire_url;
            }
            return url;
        });

        self.savedCards = ko.observableArray();

        self.selectedSavedCard = ko.observable();
        self.selectedCardType = ko.observable();

        self.isSavedCard = ko.computed(function () {
            return self.selectedCardType() === 'saved';
        });
        self.isNewCard = ko.computed(function () {
            return self.selectedCardType() === 'new';
        });

        self.newCard = ko.observable(stripeCardModel());

        self.handlers = [self];

        self.showConfirmRemoveCard = ko.observable(false);
        self.isRemovingCard = ko.observable(false);
        self.selectedCard = ko.computed(function () {
            self.showConfirmRemoveCard(false);
            if (self.isSavedCard()) {
                return self.selectedSavedCard();
            }
            return self.newCard();
        });
        self.hasAgreedToPrivacy = ko.computed(function () {
            if (self.paymentMethod() === self.CREDIT_CARD) {
                return self.selectedCard() && self.selectedCard().cardFormIsValid();
            }
            return true;
        });

        if (opts.wire_email) {
            self.wireEmails(opts.wire_email);
        }

        self.mustCreateNewCard = ko.computed(function () {
            return self.paymentIsNotComplete() && self.savedCards().length === 0;
        });
        self.canSelectCard = ko.computed(function () {
            return self.paymentIsNotComplete() && self.savedCards().length > 0;
        });

        self.isSubmitDisabled = ko.computed(function () {
            if (self.paymentMethod() === self.CREDIT_CARD) {
                return !(!! self.costItem() && self.costItem().isValid()) || self.selectedCard().isProcessing();
            } else {
                return (self.paymentProcessing());
            }
        });

        self.loadCards = function (cards) {
            _.each(cards.data, function (card) {
                var stripeCard = stripeCardModel();
                stripeCard.loadSavedData(card);
                self.savedCards.push(stripeCard);
            });
            if (self.savedCards().length > 0) {
                self.selectedCardType('saved');
            }
        };

        self.reset = function () {
            self.paymentIsComplete(false);
            self.serverErrorMsg('');
            self.newCard(stripeCardModel());
        };

        self.processPayment = function () {
            if (self.costItem().isValid() && self.paymentMethod() === self.CREDIT_CARD) {
                self.selectedCard().process(self.submitForm);
            } else {
                self.paymentProcessing(true);
                self.submitForm();
            }
        };


        self.confirmRemoveSavedCard = function () {
            self.showConfirmRemoveCard(true);
        };

        self.removeSavedCard = function () {
            self.isRemovingCard(true);
            self.showConfirmRemoveCard(false);
            $('#' + self.formId).ajaxSubmit({
                data: {
                    removeCard: true,
                },
                success: function (response) {
                    self.handleProcessingErrors(response);
                    for (var i = 0; i < self.handlers.length; i++) {
                        var handler = self.handlers[i];
                        handler.savedCards(_.filter(handler.savedCards(), function (card) {
                            return card.token() !== response.removedCard;
                        }));
                        if (!handler.savedCards().length) {
                            handler.selectedCardType('new');
                        }
                    }
                    self.isRemovingCard(false);
                },
                error: function () {
                    self.handleGeneralError();
                    self.isRemovingCard(false);
                },
            });
        };

        self.cancelRemoveSavedCard = function () {
            self.showConfirmRemoveCard(false);
        };

        self.handleGeneralError = function (response, textStatus, errorThrown) {
            errorThrown = errorThrown || 500;
            self.serverErrorMsg(self.errorMessages[errorThrown]);
            self.selectedCard().isProcessing(false);
            self.paymentProcessing(false);
        };

        self.handleProcessingErrors = function (response) {
            if (response.success) {
                self.serverErrorMsg('');
            } else {
                self.serverErrorMsg(response.error.message);
            }
            self.selectedCard().isProcessing(false);
        };

        self.handleSuccess = function (response) {
            if (response.success) {
                self.costItem().reset(response);
                if (response.wasSaved) {
                    for (var i = 0; i < self.handlers.length; i++) {
                        var handler = self.handlers[i];
                        var stripeCard = stripeCardModel();
                        stripeCard.loadSavedData(response.card);
                        handler.savedCards.push(stripeCard);
                        handler.selectedCardType('saved');
                    }
                }
                self.paymentIsComplete(true);
            }
            self.paymentProcessing(false);
            self.handleProcessingErrors(response);
        };

        return self;
    };

    paymentMethodHandler.prototype = Object.create(billingHandler.prototype);
    paymentMethodHandler.prototype.constructor = paymentMethodHandler;
    wireInvoiceHandler.prototype = Object.create(billingHandler.prototype);
    wireInvoiceHandler.prototype.constructor = wireInvoiceHandler;

    var baseCostItem = function () {
        var self = {};

        self.reset = function () {
            throw new Error("Missing implementation for reset");
        };

        self.isValid = function () {
            throw new Error("missing implementation for isValid");
        };
        return self;
    };

    var chargedCostItem = function (initData) {
        var self = {};
        self = baseCostItem.call(self, initData);

        self.balance = ko.observable();

        self.customPaymentAmount = ko.observable(self.balance());
        self.paymentAmountType = ko.observable('full');

        self.isBalanceAtMinimum = ko.computed(function () {
            try {
                var balance = parseFloat(self.balance());
                return balance - 0.5 <= 0.0;
            } catch (e) {
                return false;
            }
        });

        self.showCustomOption = ko.computed(function () {
            return ! self.isBalanceAtMinimum();
        });

        self.isAmountWithinRange = ko.computed(function () {
            try {
                var balance = parseFloat(self.balance()),
                    customAmount = parseFloat(self.customPaymentAmount());
                return balance >= customAmount && customAmount >= 0.5;
            } catch (e) {
                return false;
            }
        });

        self.maxPartialAmount = ko.computed(function () {
            return self.balance() - 0.5;
        });

        self.isLeftoverAmountEnough = ko.computed(function () {
            try {
                var balance = parseFloat(self.balance()),
                    maxPartial = parseFloat(self.maxPartialAmount()),
                    customAmount = parseFloat(self.customPaymentAmount());
                return customAmount === balance || customAmount <= maxPartial;
            } catch (e) {
                return false;
            }
        });

        self.showAmountRangeError = ko.computed(function () {
            return ! self.isAmountWithinRange();
        });

        self.showAmountLeftoverError = ko.computed(function () {
            return (! self.isLeftoverAmountEnough()) && (! self.showAmountRangeError());
        });

        self.selectPartialPayment = function () {
            self.paymentAmountType('partial');
        };

        self.isValid = ko.computed(function () {
            return self.isLeftoverAmountEnough() && self.isAmountWithinRange();
        });
        return self;
    };

    chargedCostItem.prototype = Object.create(baseCostItem.prototype);
    chargedCostItem.prototype.constructor = chargedCostItem;


    var invoice = function (initData) {
        var self = {};
        self = chargedCostItem.call(self, initData);

        self.paginatedItem = initData.paginatedItem;
        self.paginatedList = initData.paginatedList;
        self.balance(self.paginatedItem.itemData().balance);
        self.customPaymentAmount(self.balance());

        self.id = ko.computed(function () {
            return self.paginatedItem.itemData().id;
        });
        self.invoiceNumber = ko.computed(function () {
            return self.paginatedItem.itemData().invoice_number;
        });

        self.reset = function (response) {
            self.paginatedList.refreshList(self.paginatedItem);
            if (response.success) {
                var oldBalance = self.paginatedList.totalDue();
                self.paginatedList.totalDue(oldBalance - response.changedBalance);
            }
        };
        return self;
    };

    invoice.prototype = Object.create(chargedCostItem.prototype);
    invoice.prototype.constructor = invoice;

    /* initData contains totalBalance and paginatedListModel */
    var totalCostItem = function (initData) {
        var self = {};
        self = chargedCostItem.call(self, initData);

        self.balance(initData.totalBalance);
        self.customPaymentAmount(self.balance());

        self.id = null;

        self.reset =  function () {
            initData.paginatedListModel.refreshList();
        };

        return self;
    };

    totalCostItem.prototype = Object.create(chargedCostItem.prototype);
    totalCostItem.prototype.constructor = totalCostItem;

    var prepaymentItems = function (data) {
        var self = {};
        self = baseCostItem.call(self, data);

        self.products = data.products;
        self.features = data.features;
        self.general_credit = data.general_credit;

        self.amount = ko.computed(function () {
            var productSum = _.reduce(self.products(), function (memo, product) {
                return memo + parseFloat(product.addAmount());
            }, 0);

            var featureSum = _.reduce(self.features(), function (memo, feature) {
                return memo + parseFloat(feature.addAmount());
            }, 0);
            var sum = productSum + featureSum + parseFloat(self.general_credit().addAmount());
            return isNaN(sum) ? 0.0 : sum;
        });

        self.reset = function (response) {
            var items = self.products().concat(self.features());
            _.each(response.balances, function (balance) {
                var updateBalance = _.find(items, function (item) {
                    return item.creditType() === balance.type;
                });
                if (updateBalance) {
                    updateBalance.amount(balance.balance);
                }
            });
        };

        self.isValid = function () {
            return self.amount() >= 0.5;
        };
        return self;
    };

    var creditCostItem = function (initData) {
        var self = {};
        self = baseCostItem.call(self, initData);

        self.creditType = ko.observable(initData.creditType);
        self.category = ko.observable(initData.category);
        self.creditItem = initData.creditItem;
        self.amount = ko.observable(0.5);

        self.isPlanCredit = ko.computed(function () {
            return self.category() === 'product';
        });

        self.isSMSCredit = ko.computed(function () {
            return self.category() === 'feature' && self.creditType() === 'SMS';
        });

        self.isUserCredit = ko.computed(function () {
            return self.category() === 'feature' && self.creditType() === 'User';
        });

        self.reset = function (response) {
            self.creditItem.amount(response.balance);
        };

        self.isValid = function () {
            return self.amount() >= 0.5;
        };
        return self;
    };

    creditCostItem.prototype = Object.create(baseCostItem.prototype);
    creditCostItem.prototype.constructor = creditCostItem;

    var stripeCardModel = function () {
        var self = {};

        self.number = ko.observable();
        self.cvc = ko.observable();
        self.expMonth = ko.observable();
        self.expYear = ko.observable();
        self.errorMsg = ko.observable();
        self.token = ko.observable();
        self.isTestMode = ko.observable(false);
        self.isProcessing = ko.observable(false);
        self.newSavedCard = ko.observable(false);

        self.autopayCard = ko.computed(function () {
            if (!self.newSavedCard()) {
                return false;
            }
        });

        self.showCardData = ko.computed(function () {
            return ! self.isProcessing();
        });
        self.cardType = ko.observable();
        self.isSaved = ko.observable(false);

        self.cardFormIsValid = ko.computed(function () {
            return self.isSaved() || !self.isSaved();
        });

        self.showErrors = ko.computed(function () {
            return !! self.errorMsg();
        });
        self.cleanedNumber = ko.computed(function () {
            if (self.number()) {
                return self.number().split('-').join('');
            }
            return null;
        });

        self.cardName = ko.computed(function () {
            return self.cardType() + ' ' + self.number() + ' exp ' + self.expMonth() + '/' + self.expYear();
        });


        self.loadSavedData = function (data) {
            self.number('************' + data.last4);
            self.cardType(data.type);
            self.expMonth(data.exp_month);
            self.expYear(data.exp_year);
            self.token(data.id);
            self.cvc('****');
            self.isSaved(true);
        };

        self.process = function (callbackOnSuccess) {
            self.isProcessing(true);
            if (self.isSaved() && self.token()) {
                callbackOnSuccess();
                return;
            }
            Stripe.card.createToken({
                number: self.number(),
                cvc: self.cvc(),
                exp_month: self.expMonth(),
                exp_year: self.expYear(),
            }, function (status, response) {
                if (response.error) {
                    self.errorMsg(response.error.message);
                    self.isProcessing(false);
                } else {
                    self.errorMsg('');
                    self.token(response.id);
                    self.isTestMode(!response.livemode);
                    if (self.token()) {
                        callbackOnSuccess();
                    } else {
                        self.isProcessing(false);
                        self.errorMsg('Response from Stripe did not complete properly.');
                    }
                }
            });
        };

        return self;
    };
    return {
        wireInvoiceHandler: wireInvoiceHandler,
        paymentMethodHandler: paymentMethodHandler,
        invoice: invoice,
        totalCostItem: totalCostItem,
        prepaymentItems: prepaymentItems,
        creditCostItem: creditCostItem,
    };
});
