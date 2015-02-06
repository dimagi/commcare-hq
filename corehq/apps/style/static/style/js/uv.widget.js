// UserVoice widget setup
$(document).ready(function() {
    'use strict';
    var data,
        defaults,
        uvBtnId = '#uvSubmitIdea',
        $uvBtn = $(uvBtnId);

    if (!$uvBtn.length) {
        return;
    }

    // Include the UserVoice JavaScript SDK (only needed once on a page)
    window.UserVoice=window.UserVoice||[];(function(){var uv=document.createElement('script');uv.type='text/javascript';uv.async=true;uv.src='//widget.uservoice.com/PeUfQwynga75cBUaAV8Ew.js';var s=document.getElementsByTagName('script')[0];s.parentNode.insertBefore(uv,s)})();

    //
    // UserVoice Javascript SDK developer documentation:
    // https://www.uservoice.com/o/javascript-sdk
    //

    // UV crashes hard when it receives undefined as a value. Need to ensure defaults.
    defaults = {
        userEmail: 'Unknown email address',
        userName: 'Unknown name'
    };

    data = _.defaults(defaults, $uvBtn.data());

    // Widget configuration
    window.UserVoice.push(['set', {
        accent_color: 'rgb(15, 64, 147)',
        contact_enabled: false,
        smartvote_enabled: false,
        forum_id: '283063'
    }]);

    // Identify the user and pass traits
    window.UserVoice.push(['identify', {
        email: data.userEmail,
        name: data.userName,
    }]);

    window.UserVoice.push(['addTrigger', uvBtnId]);

    $uvBtn.click(function() {
        ga_track_event('Toolbar', 'Submit an Idea', data.domain);
    });
});
