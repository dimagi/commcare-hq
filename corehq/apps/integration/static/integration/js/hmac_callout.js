/* globals CryptoJS */

hqDefine("integration/js/hmac_callout", ["hqwebapp/js/initial_page_data"], function (initialPageData) {
    var randomString = function (length) {
        var text = "";
        var possible = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789";
        for (var i = 0; i < length; i++) {
            text += possible.charAt(Math.floor(Math.random() * possible.length));
        }
        return text;
    };

    var digest = function (key, nonce, timestamp) {
        return CryptoJS.SHA512([nonce, key, timestamp].join(""));
    };

    var encode64 = function (message) {
        return CryptoJS.enc.Base64.stringify(message);
    };

    var hash = function (message) {
        return CryptoJS.SHA512(message);
    };

    var hmac = function (message, secret) {
        return CryptoJS.HmacSHA512(message, secret);
    };

    var performCallout = function (anchor) {
        var url = new URL(anchor.href);

        var path = url.pathname;
        url.searchParams.sort();

        var variables = url.searchParams.toString();

        var hashedBody = hash(variables);

        var dest = anchor.href.split('?')[0];

        var nonce = randomString(32);
        var timestamp = Date.now();

        var keyDigest = digest(initialPageData.get('hmac_api_key'), nonce, timestamp);

        var message = [path, variables, keyDigest, hashedBody].join("");
        var signature = hmac(message, initialPageData.get('hmac_hashed_secret'));
        var encodedSignature = encode64(signature);

        var args = {
            'nonce': nonce,
            'timestamp': timestamp,
            'variables': variables,
            'signature': encodedSignature};

        postForm(args, dest);
    };

    var postForm = function (data, dest) {
        var form = document.createElement("form");

        form.method = "POST";
        form.action = dest;
        form.target = "hmac_callout";

        for (var key in data) {
            var element = document.createElement("input");
            element.name = key;
            element.value = data[key];

            form.appendChild(element);
        }

        document.body.appendChild(form);

        form.submit();

        document.body.removeChild(form);
    };

    window.HMACCallout = performCallout;

    return {
        performCallout: performCallout,
    };
});
