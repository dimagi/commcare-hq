from django.utils.translation import ugettext_noop

STATICALLY_ANALYZABLE_TRANSLATIONS = [
    ugettext_noop('1 Day'),
    ugettext_noop('1 hour'),
    ugettext_noop('1.x'),
    ugettext_noop('1.0'),
    ugettext_noop('1.5'),
    ugettext_noop('10'),
    ugettext_noop('12 hours'),
    ugettext_noop('15 minutes'),
    ugettext_noop('160'),
    ugettext_noop('2 hours'),
    ugettext_noop('2.0'),
    ugettext_noop('2.x'),
    ugettext_noop('20'),
    ugettext_noop('24 hours'),
    ugettext_noop('30 minutes'),
    ugettext_noop('4 hours'),
    ugettext_noop('40'),
    ugettext_noop('5 Days'),
    ugettext_noop('5'),
    ugettext_noop('6 hours'),
    ugettext_noop('8 hours'),
    ugettext_noop('80'),
    ugettext_noop('Admin Password'),
    ugettext_noop('Advanced'),
    ugettext_noop('After login, the application will look at the profile\'s defined reference for the authoritative location of the newest version. This check will occur with some periodicity since the last successful check based on this property. freq-never disables the automatic check.'),
    ugettext_noop('Allow mobile workers in the same case sharing group to share case lists.  Read more on the <a href="https://help.commcarehq.org/display/commcarepublic/Case+Sharing">Help Site</a>'),
    ugettext_noop('Allow mobile workers to access the web-based version of your application. Read more on the <a href="https://help.commcarehq.org/display/commcarepublic/Using+Web+Apps">Help Site</a>'),
    ugettext_noop('Allow visitors to use this application without a login.'),
    ugettext_noop('Alphanumeric'),
    ugettext_noop('Amount of time previously submitted forms remain accessible in the CommCare app.'),
    ugettext_noop('Android Settings'),
    ugettext_noop('Anonymous Usage'),
    ugettext_noop('Any positive integer. Represents period of purging in days.'),
    ugettext_noop('App Aware Location Fixture Format'),
    ugettext_noop('App Version'),
    ugettext_noop('Audio'),
    ugettext_noop('Auto Capture Location<br />(all forms)'),
    ugettext_noop('Auto Update Frequency'),
    ugettext_noop('Auto-Resize Images'),
    ugettext_noop('Auto-Sync Frequency'),
    ugettext_noop('Auto-login'),
    ugettext_noop('Auto-manage URLs'),
    ugettext_noop('Automatic'),
    ugettext_noop('Automatically resizes images within forms. Follow <a href=\'https://confluence.dimagi.com/display/commcarepublic/Auto-Resize+Images+on+Android\'> the instructions here</a> to determine which value to use.'),
    ugettext_noop('Automatically trigger a two-way sync on a regular schedule'),
    ugettext_noop('Basic'),
    ugettext_noop('Both Hierarchical and Flat Fixture'),
    ugettext_noop('Build Settings'),
    ugettext_noop('Case Sharing'),
    ugettext_noop('Choose an image to replace the default CommCare Home Screen logo'),
    ugettext_noop('Choose to label the login buttons with Icons or Text'),
    ugettext_noop('Choose whether or not mobile workers can view previously submitted forms.'),
    ugettext_noop('Choose whether or not to display the \'Incomplete\' button on the ODK home screen'),
    ugettext_noop('CommCare'),
    ugettext_noop('CommCare Home Screen Logo'),
    ugettext_noop('CommCare LTS'),
    ugettext_noop('CommCare Sense'),
    ugettext_noop('CommCare Version'),
    ugettext_noop('Configure for low-literate users, J2ME only'),
    ugettext_noop('Configure form menus display. For per-module option turn on grid view for the form\'s menu in a module under module\'s settings page. Read more on the <a target="_blank" href="https://help.commcarehq.org/display/commcarepublic/Grid+View+for+Form+and+Module+Screens">Help Site</a>.'),
    ugettext_noop('Custom Base URL'),
    ugettext_noop('Custom Keys'),
    ugettext_noop('Custom Suite File'),
    ugettext_noop('Custom Suite'),
    ugettext_noop('Daily Log Sending Frequency'),
    ugettext_noop('Daily'),
    ugettext_noop('Data and Sharing'),
    ugettext_noop('Days allowed without syncing before triggering a warning'),
    ugettext_noop('Days for Review'),
    ugettext_noop('Default Map Tileset'),
    ugettext_noop('Demo Logo'),
    ugettext_noop('Determines if the server automatically attempts to send data to the phone (Two-Way), or only attempt to send data on demand (Push Only); projects using Case Sharing should choose Two-Way. If set to Push Only, the Auto-Sync Frequency and Unsynced Time Limit settings will have no effect.'),
    ugettext_noop('Determines whether phone keys will type letters or numbers by default when typing in the password field.'),
    ugettext_noop('Disable'),
    ugettext_noop('Disabled'),
    ugettext_noop('Display root menu as a list or grid. Read more on the <a target="_blank" href="https://help.commcarehq.org/display/commcarepublic/Grid+View+for+Form+and+Module+Screens">Help Site</a>.'),
    ugettext_noop('Enable Menu Display Setting Per-Module'),
    ugettext_noop('Enable'),
    ugettext_noop('Enabled'),
    ugettext_noop('Extra Key Action'),
    ugettext_noop('For mobile map displays, chooses a base tileset for the underlying map layer'),
    ugettext_noop('Form Entry Style'),
    ugettext_noop('Forms Menu Display'),
    ugettext_noop('Forms are Never Removed'),
    ugettext_noop('Full Keyboard'),
    ugettext_noop('Full Resize'),
    ugettext_noop('Full'),
    ugettext_noop('Fuzzy Search'),
    ugettext_noop('General Settings'),
    ugettext_noop('Generic'),
    ugettext_noop('Grid'),
    ugettext_noop('Half Resize'),
    ugettext_noop('High Density'),
    ugettext_noop('Horizontal Resize'),
    ugettext_noop('How Send All Unsent functionality is presented to the user'),
    ugettext_noop('How should Commcare load the the video files in the application. By default Commcare will try to load them instantly'),
    ugettext_noop('How often CommCare mobile should attempt to check for a new, released application version.'),
    ugettext_noop('How often the phone should attempt to purge any cached storage which may have expired'),
    ugettext_noop('Hybrid'),
    ugettext_noop('Icons'),
    ugettext_noop('If automatic is enabled, forms will attempt to send on their own without intervention from the user. If manual is enabled, the user must manually decide when to attempt to send forms.'),
    ugettext_noop('If multimedia validation is enabled, CommCare will perform an additional check after installing your app to ensure that all of your multimedia is present on the phone before allowing the app to run. It is recommended for deployment, but will make your app unable to run if multimedia is enabled.'),
    ugettext_noop('Image Compatibility on Multiple Devices'),
    ugettext_noop('In normal mode, users log in each time with their username and password. In auto-login mode, once a user (not the \'admin\' or \'demo\' users) has logged in, the application will start up with that user already logged in.'),
    ugettext_noop('Incomplete Forms'),
    ugettext_noop('Item Selection Mode'),
    ugettext_noop('Java Phone General Settings'),
    ugettext_noop('Java Phone Platform'),
    ugettext_noop('Java Phone User Interface Settings'),
    ugettext_noop('Just One Day'),
    ugettext_noop('Language cycles through any available translations. Audio plays the question\'s audio if available. NOTE: If audio is selected, a question\'s audio will not be played by default when the question is displayed.'),
    ugettext_noop('Languages'),
    ugettext_noop('Length of time after which you will be logged out automatically'),
    ugettext_noop('List'),
    ugettext_noop('Load video files lazily'),
    ugettext_noop('Location Fixture format that is provided in the restore for this app'),
    ugettext_noop('Log Case Detail Views'),
    ugettext_noop('Logging Enabled'),
    ugettext_noop('Login Buttons'),
    ugettext_noop('Login Duration'),
    ugettext_noop('Login Logo'),
    ugettext_noop('Loose Media Mode'),
    ugettext_noop('Loose'),
    ugettext_noop('Low Density'),
    ugettext_noop('Manual'),
    ugettext_noop('Medium Density'),
    ugettext_noop('Minimum duration between updates to mobile report data (hours).'),
    ugettext_noop('Mobile Reports Update Frequency'),
    ugettext_noop('Mobile UCR Restore Version'),
    ugettext_noop('Modules Menu Display'),
    ugettext_noop('Multimedia Validation'),
    ugettext_noop('Multiple Questions per Screen displays a running list of questions on the screen at the same time. One Question per Screen displays each question independently. Note: OQPS does not support some features'),
    ugettext_noop('Multiple Questions per Screen'),
    ugettext_noop('Must correspond to the password format specified below.'),
    ugettext_noop('Native (International)'),
    ugettext_noop('Never'),
    ugettext_noop('No (NOT RECOMMENDED)'),
    ugettext_noop('No Users Mode'),
    ugettext_noop('No Validation'),
    ugettext_noop('No'),
    ugettext_noop('Nokia S40 (default)'),
    ugettext_noop('Nokia S60'),
    ugettext_noop('None'),
    ugettext_noop('Normal Scrolling'),
    ugettext_noop('Normal'),
    ugettext_noop('Number of unsent forms on phone before triggering warning text'),
    ugettext_noop('Numeric Selection mode will display information about questions for longer and require more input from the user. Normal Scrolling will proceed to the next question whenever enough information is provided.'),
    ugettext_noop('Numeric Selection'),
    ugettext_noop('Numeric'),
    ugettext_noop('OTA Restore Tolerance'),
    ugettext_noop('Off'),
    ugettext_noop('On CommCare Android, have this form automatically capture the user\'s current geo-location.\n'),
    ugettext_noop('On'),
    ugettext_noop('Once a Month'),
    ugettext_noop('Once a Week'),
    ugettext_noop('One Month'),
    ugettext_noop('One Question per Screen'),
    ugettext_noop('One Week'),
    ugettext_noop('One Year'),
    ugettext_noop('Only Flat Fixture'),
    ugettext_noop('Only Hierarchical Fixture'),
    ugettext_noop('Oops! This setting has been discontinued. We recommend you change this setting to Version 2, and it will no longer appear on your settings page.'),
    ugettext_noop('Password Format'),
    ugettext_noop('Practice Mobile Worker'),
    ugettext_noop('Profile URL'),
    ugettext_noop('Project Default'),
    ugettext_noop('Prompt Updates to Latest CommCare Version'),
    ugettext_noop('Prompt Updates to Latest Released App Version'),
    ugettext_noop('Purge Frequency'),
    ugettext_noop('Push Only'),
    ugettext_noop('Required'),
    ugettext_noop('Restrict this app to the selected CommCare flavor'),
    ugettext_noop('Roman'),
    ugettext_noop('Saved Forms'),
    ugettext_noop('Satellite'),
    ugettext_noop('Select the mobile worker to use as a practice user for this application'),
    ugettext_noop('Send Data Over HTTP'),
    ugettext_noop('Send Data'),
    ugettext_noop('Send Forms Mode'),
    ugettext_noop('Server User Registration'),
    ugettext_noop('Set to skip if your deployment does not require users to register with the server. Note that this will likely result in OTA Restore and other features being unavailable.'),
    ugettext_noop('Short'),
    ugettext_noop('Simple (FOR TESTING ONLY: crashes with any unrecognized user-defined translations)'),
    ugettext_noop('Skip'),
    ugettext_noop('Strict'),
    ugettext_noop('Sync Mode'),
    ugettext_noop('Target CommCare Flavor'),
    ugettext_noop('Terrain'),
    ugettext_noop('Text Input'),
    ugettext_noop('Text'),
    ugettext_noop("The kind of Java phone you want to run the application on"),
    ugettext_noop('This value will set whether the login screen uses customizable icons for login and demo mode options or uses the standard buttons with labels.'),
    ugettext_noop('This will determine how images you select for your questions will be resized to fit the screen. Horizontal will stretch/compress the image to fit perfectly horizontally while scaling to height to maintain the aspect ratio. Full Resize will try to be clever and find the ideal vertical/horizontal scaling for the screen. Half Resize will do the same but with half the area.'),
    ugettext_noop('This will set the amount of time you will remain logged in before automatically being logged out.'),
    ugettext_noop('This will show or hide the \'Incomplete\' button on the CommCare ODK home screen. Turning this off will prevent users from saving incomplete forms.'),
    ugettext_noop('This will show or hide the \'Saved\' button on the CommCare ODK home screen. Turning this off will prevent users from saving forms locally.'),
    ugettext_noop('Three Months'),
    ugettext_noop('Translations Strategy'),
    ugettext_noop('Twice a Month'),
    ugettext_noop('Two Weeks'),
    ugettext_noop('Two-Way Sync'),
    ugettext_noop('Unsent Form Limit'),
    ugettext_noop('Unsynced Time Limit'),
    ugettext_noop('Update on every sync'),
    ugettext_noop('Upload a file to serve as a demo logo on Android phones'),
    ugettext_noop('Upload a file to serve as a login logo on Android phones'),
    ugettext_noop('Use Secure Submissions'),
    ugettext_noop('Use project level setting'),
    ugettext_noop('Use a different base URL for all app URLs. This makes the phone send forms, sync and look for updates from a differnent URL. Main use case is to allow migrating ICDS to a new cluster.'),
    ugettext_noop('User Login Mode'),
    ugettext_noop('Validate Multimedia'),
    ugettext_noop('Version 1 translations (old)'),
    ugettext_noop('Version 2 translations (recommended)'),
    ugettext_noop('Version of mobile UCRs to use. Read more on the  <a target="_blank" href="https://help.commcarehq.org/display/ccinternal/Moving+to+Mobile+UCR+V2">Help Site</a>'),
    ugettext_noop('We frequently release new versions of CommCare Mobile. Use the latest version to take advantage of new features and bug fixes. Note that if you are using CommCare for Android you must also update your version of CommCare from the Google Play Store.'),
    ugettext_noop('We suggest moving to CommCare 2.0 and above, unless your project is using referrals'),
    ugettext_noop('Web App'),
    ugettext_noop('Weekly Log Sending Frequency'),
    ugettext_noop('Weekly'),
    ugettext_noop("What characters to allow users to input"),
    ugettext_noop('What kind of log transmission the phone should attempt on a daily basis (submitted to PostURL)'),
    ugettext_noop('What kind of log transmission the phone should attempt on a weekly basis (submitted to PostURL)'),
    ugettext_noop('What the \'Extra Key\' (# on Nokia Phones) does when pressed'),
    ugettext_noop('What user interface style should be used during form entry.'),
    ugettext_noop('When a value is selected, this feature controls the display size of any user-provided image such that it will be consistent with the size of the original image file, and consistent across devices. Follow <a href=\'https://confluence.dimagi.com/display/commcarepublic/Image+Sizing+with+Multiple+Android+Device+Models\'> the instructions here</a> to determine which value to use.'),
    ugettext_noop('When auto-sync is enabled CommCare will attempt to submit forms and synchronize the user\'s data after logging in with the frequency chosen.'),
    ugettext_noop('When loose media mode is set to yes, CommCare will search for alternative media formats for any media that it cannot play. If CommCare attempts to play a file at jr://file/media/prompt_one.mp3 and mp3 files are not supported, the media directory will be searched for other files named prompt_one with alternative extensions which may be supported, for instance prompt_one.wav, and play that instead.'),
    ugettext_noop('When the phone has this number of unsynced forms stored locally CommCare will trigger a warning'),
    ugettext_noop('When this many days have passed without the user syncing CommCare will trigger a warning'),
    ugettext_noop('When you select this box, your data will no longer be encrypted.  Because of changes regarding Java phone security certificates, it will be necessary to send data over HTTP to continue sending data to CommCare.'),
    ugettext_noop('Whenever Possible'),
    ugettext_noop('Whether CommCare should search for alternative formats of incompatible media files.'),
    ugettext_noop('Whether CommCare should validate that all external multimedia is installed before letting the user run the app.'),
    ugettext_noop('Whether OTA Restore is tolerant of failures, ambiguity, duplicate registrations, etc (and proceeds as best it can), or whether it fails immediately in these cases.'),
    ugettext_noop('Whether form entry is optimized for speed, or for new users.'),
    ugettext_noop('Whether logging of incidents should be activated on the client.'),
    ugettext_noop('Whether or not the phone collects, saves, and sends data.'),
    ugettext_noop('Whether searches can match similar strings'),
    ugettext_noop('Whether searches on the phone will match similar strings. IE: \'Jhon\' will match \'John\''),
    ugettext_noop('Whether to log each time a user views case details. May reduce mobile performance.'),
    ugettext_noop('Whether to show the user login screen'),
    ugettext_noop('Whether users registered on the phone need to be registered with the submission server.'),
    ugettext_noop('WinMo'),
    ugettext_noop('X-High Density'),
    ugettext_noop('XX-High Density'),
    ugettext_noop('XXX-High Density'),
    ugettext_noop('Yes'),
    ugettext_noop('disabled'),
]
