var PaymentMethodHandler = function (errorMessages, submitBtnText) {
    'use strict';
    var self = this;

    self.errorMessages = errorMessages || {};
    self.submitBtnText = submitBtnText;

    self.costItem = ko.observable();
    self.hasCostItem = ko.computed(function () {
        return !! self.costItem();
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

    self.newCard = ko.observable(new StripeCard());

    self.showConfirmRemoveCard = ko.observable(false);
    self.isRemovingCard = ko.observable(false);
    self.selectedCard = ko.computed(function () {
        self.showConfirmRemoveCard(false);
        if (self.isSavedCard()) {
            return self.selectedSavedCard();
        }
        return self.newCard();
    });
    self.hasAgreedToPrivacy = ko.computed(function() {
        return self.selectedCard() && self.selectedCard().cardFormIsValid();
    });

    self.paymentIsComplete = ko.observable(false);
    self.paymentIsNotComplete = ko.computed(function () {
        return ! self.paymentIsComplete();
    });

    self.mustCreateNewCard = ko.computed(function () {
        return self.paymentIsNotComplete() && self.savedCards().length == 0;
    });
    self.canSelectCard = ko.computed(function () {
        return self.paymentIsNotComplete() && self.savedCards().length > 0;
    });

    self.isSubmitDisabled = ko.computed(function () {
        return !(!! self.costItem() && self.costItem().isValid()) || self.selectedCard().isProcessing();
    });

    self.serverErrorMsg = ko.observable();
    self.showServerErrorMsg = ko.computed(function () {
        return !! self.serverErrorMsg();
    });

    self.loadCards = function (cards) {
        _.each(cards.data, function (card) {
            var stripe_card = new StripeCard();
            stripe_card.loadSavedData(card);
            self.savedCards.push(stripe_card);
        });
        if (self.savedCards().length > 0) {
            self.selectedCardType('saved');
        }
    };

    self.reset = function () {
        self.paymentIsComplete(false);
        self.serverErrorMsg('');
        self.newCard(new StripeCard());
    };

    self.processPayment = function () {
        if (self.costItem().isValid()) {
            self.selectedCard().process(self.submitForm);
        }
    };

    self.submitForm = function () {
        $('#payment-form').ajaxSubmit({
            success: function (response) {
                if (response.success) {
                    self.costItem().reset(response);
                    self.newCard(new StripeCard());
                    if (response.wasSaved) {
                        var stripe_card = new StripeCard();
                        stripe_card.loadSavedData(response.card);
                        self.savedCards.push(stripe_card);
                        self.selectedCardType('saved');
                    }
                    self.paymentIsComplete(true);
                }
                self.handleProcessingErrors(response);
            },
            error: self.handleGeneralError
        });
    };

    self.confirmRemoveSavedCard = function () {
        self.showConfirmRemoveCard(true);
    };

    self.removeSavedCard = function () {
        self.isRemovingCard(true);
        self.showConfirmRemoveCard(false);
        $('#payment-form').ajaxSubmit({
            data: {
                removeCard: true
            },
            success: function (response) {
                self.handleProcessingErrors(response);
                self.savedCards(_.filter(self.savedCards(), function (card) {
                    return card.token() !== response.removedCard;
                }));
                if (self.savedCards().length == 0) {
                    self.selectedCardType('new');
                }
                self.isRemovingCard(false);
            },
            error: function () {
                self.handleGeneralError();
                self.isRemovingCard(false);
            }
        });
    };

    self.cancelRemoveSavedCard = function () {
        self.showConfirmRemoveCard(false);
    };

    self.handleGeneralError = function (response, textStatus, errorThrown) {
        errorThrown = errorThrown || 500;
        self.serverErrorMsg(self.errorMessages[errorThrown]);
        self.selectedCard().isProcessing(false);
    };

    self.handleProcessingErrors = function (response) {
        if (response.success) {
            self.serverErrorMsg('');
        } else {
            self.serverErrorMsg(response.error.message);
        }
        self.selectedCard().isProcessing(false);
    };
};

var BaseCostItem = function (initData) {
    'use strict';
    var self = this;

    self.reset = function (response) {
        throw new Error("Missing implementation for reset");
    };

    self.isValid = function () {
        throw new Error("missing implementation for isValid");
    };

};

var ChargedCostItem = function (initData) {
    'use strict';
    BaseCostItem.call(this, initData);
    var self = this;

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
            return customAmount == balance || customAmount <= maxPartial;
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

    self.reset =  function (response) {
        self.customPaymentAmount(self.balance());
        self.paymentAmountType('full');
    };

    self.isValid = ko.computed(function () {
        return self.isLeftoverAmountEnough() && self.isAmountWithinRange();
    });
};

ChargedCostItem.prototype = Object.create( BaseCostItem.prototype );
ChargedCostItem.prototype.constructor = ChargedCostItem;


var Invoice = function (initData) {
    'use strict';
    ChargedCostItem.call(this, initData);
    var self = this;

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
        // TODO - use inheritance instead of duplicating code (tricky)
        self.customPaymentAmount(self.balance());
        self.paymentAmountType('full');
        self.paginatedList.refreshList(self.paginatedItem);
    };
};

Invoice.protoptye = Object.create( ChargedCostItem.prototype );
Invoice.prototype.constructor = Invoice;

var TotalCostItem = function (initData) {
    'use strict';
    ChargedCostItem.call(this, initData);
    var self = this;

    self.balance(initData.totalBalance);
    self.customPaymentAmount(self.balance());

    self.id = null; // TODO remove once cost-item-template does not need this
};

TotalCostItem.protoptye = Object.create( ChargedCostItem.prototype );
TotalCostItem.prototype.constructor = TotalCostItem;

var CreditCostItem = function (initData) {
   'use strict';
    BaseCostItem.call(this, initData);
    var self = this;

    self.creditType = ko.observable(initData.creditType);
    self.category = ko.observable(initData.category);
    self.creditItem = initData.creditItem;
    self.amount = ko.observable(0.5);

    self.isPlanCredit = ko.computed(function () {
        return self.category() == 'product';
    });

    self.isSMSCredit = ko.computed(function () {
        return self.category() == 'feature' && self.creditType() == 'SMS';
    });

    self.isUserCredit = ko.computed(function () {
        return self.category() == 'feature' && self.creditType() == 'User';
    });

    self.reset = function (response) {
        self.creditItem.amount(response.balance);
    };

    self.isValid = function () {
        return self.amount() >= 0.5;
    };
};

CreditCostItem.ptotoptye = Object.create( BaseCostItem.prototype );
CreditCostItem.prototype.constructor = CreditCostItem;

var StripeCard = function () {
    'use strict';
    var self = this;

    self.number = ko.observable();
    self.cvc = ko.observable();
    self.expMonth = ko.observable();
    self.expYear = ko.observable();
    self.errorMsg = ko.observable();
    self.token = ko.observable();
    self.isTestMode = ko.observable(false);
    self.isProcessing = ko.observable(false);
    self.agreedToPrivacyPolicy = ko.observable(false);
    self.showCardData = ko.computed(function () {
       return ! self.isProcessing();
    });
    self.cardType = ko.observable();
    self.isSaved = ko.observable(false);

    self.cardFormIsValid = ko.computed(function () {
        return self.isSaved() || (!self.isSaved() && self.agreedToPrivacyPolicy());
    });

    self.showErrors = ko.computed(function () {
        return !! self.errorMsg();
    });
    self.cleanedNumber = ko.computed(function () {
        if (self.number()) return self.number().split('-').join('');
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
            exp_year: self.expYear()
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
};
