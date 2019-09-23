hqDefine('users/js/accept_invite', [
    'registration/js/login', // contains password obfuscation & login requirements
    'registration/js/password', // contains draconian password enforcement
    'hqwebapp/js/captcha',
], function () {});
