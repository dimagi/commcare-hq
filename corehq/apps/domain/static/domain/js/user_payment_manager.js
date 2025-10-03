/**
 *  This module requires initial page data to provide "stripe_public_key".
 *  It also requires a container with the class stripe-card-container, which is where the credit card UI will be
 *  mounted.
 */
import $ from "jquery";
import ko from "knockout";
import { Modal } from 'bootstrap5';
import { createStripeToken, getCardElementPromise } from "accounting/js/stripe";
import initialPageData from "hqwebapp/js/initial_page_data";

const newUserCard = (data, cardManager) => {
    let self = {};

    // This assumes this model won't be created until the page is loaded,
    // which is reasonable because knockout bindings don't get applied until then.
    self.cardElementMounted = false;
    self.cardElementPromise = getCardElementPromise(initialPageData.get("stripe_public_key"));
    self.cardElementPromise.then((cardElement) => {
        cardElement.mount('.stripe-card-container');
        self.cardElementMounted = true;
    });
    self.cardModalId = 'card-modal';
    self.successModalId = 'user-card-success-modal';

    const mapping = {
        observe: ['isAutopay', 'token'],
    };

    self.wrap = (data) => {
        ko.mapping.fromJS(data, mapping, self);
    };
    self.reset = () => {
        self.wrap({'isAutopay': false, 'token': ''});
        if (self.cardElementMounted) {
            self.cardElementPromise.then((cardElement) => {
                cardElement.clear();
            });
        }
    };
    self.reset();

    self.unwrap = () => {
        return {token: self.token(), autopay: self.isAutopay()};
    };

    self.isTestMode = ko.observable(false);
    self.isProcessing = ko.observable(false);
    self.errorMsg = ko.observable('');

    const submit = () => {
        // Sends the new card to HQ
        return $.ajax({
            type: "POST",
            url: data.url,
            data: self.unwrap(),
            success: (data) => {
                const cardModal = new Modal(document.getElementById(self.cardModalId));
                cardModal.hide();
                const successModal = new Modal(document.getElementById(self.successModalId));
                successModal.show();

                cardManager.wrap(data);
                self.reset();
            },
        }).fail((data) => {
            const response = JSON.parse(data.responseText);
            self.errorMsg(response.error);
        }).always(() => {
            self.isProcessing(false);
        });
    };

    const handleStripeResponse = (response) => {
        if (response.error) {
            self.isProcessing(false);
            self.errorMsg(response.error.message);
        } else {
            self.errorMsg('');
            self.token(response.token.id);
            submit();
        }
    };

    self.saveCard = () => {
        self.isProcessing(true);
        createStripeToken(handleStripeResponse);
    };

    return self;
};

const savedUserCard = (card, baseUrl, cardManager) => {
    let self = {};
    const mapping = {
        include: ['brand', 'last4', 'exp_month','exp_year', 'is_autopay', 'other_autopay_domains'],
        copy: ['url', 'token'],
    };

    self.wrap = (data) => {
        ko.mapping.fromJS(data, mapping, self);
        self.url = baseUrl + card.token + '/';
    };
    self.wrap(card);

    self.setAutopay = () => {
        cardManager.autoPayButtonEnabled(false);
        self.submit({is_autopay: true}).always(() => {
            cardManager.autoPayButtonEnabled(true);
        });
    };

    self.unSetAutopay = () => {
        cardManager.autoPayButtonEnabled(false);
        self.submit({is_autopay: false}).always(() => {
            cardManager.autoPayButtonEnabled(true);
        });
    };

    self.isDeleting = ko.observable(false);
    self.deleteErrorMsg = ko.observable('');
    self.deleteCard = (card, button) => {
        self.isDeleting(true);
        self.deleteErrorMsg = ko.observable('');
        cardManager.cards.destroy(card);
        $.ajax({
            type: "DELETE",
            url: self.url,
            success: (data) => {
                cardManager.wrap(data);

                const closestModal = new Modal(button.currentTarget.closest(".modal"));
                closestModal.hide();
                const successModal = new Modal(document.getElementById(self.successModalId));
                successModal.show();
            },
        }).fail((data) => {
            const response = JSON.parse(data.responseText);
            self.deleteErrorMsg(response.error);
            if (response.cards) {
                cardManager.wrap(response);
            }
        }).always(() => {
            self.isDeleting(false);
        });
    };

    self.submit = (data) => {
        return $.ajax({
            type: "POST",
            url: self.url,
            data: data,
            success: (data) => {
                cardManager.wrap(data);
            },
        }).fail((data) => {
            const response = JSON.parse(data.responseText);
            alert(response.error);
        });
    };

    return self;
};


export function userPaymentManager(data) {
    let self = {};
    const mapping = {
        'cards': {
            create: (card) => {
                return savedUserCard(card.data, data.url, self);
            },
        },
    };

    self.wrap = (data) => {
        ko.mapping.fromJS(data, mapping, self);
    };
    self.wrap(data);

    self.autoPayButtonEnabled = ko.observable(true);
    self.newCard = newUserCard({
        url: data.url,
    }, self);

    return self;
}
