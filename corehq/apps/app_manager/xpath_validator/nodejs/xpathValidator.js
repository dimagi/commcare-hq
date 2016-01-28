var fs = require('fs');
var data = fs.readFileSync('/dev/stdin').toString();
var allowCaseHashtags = process.argv.indexOf('--allow-case-hashtags') !== -1;

var parser = require('./xpathConfig').configureHashtags(allowCaseHashtags);

try {
    parser.parse(data);
} catch (e) {
    console.log(e.message);
    process.exit(1);
}
process.exit(0);
