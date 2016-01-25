var xpath = require('js-xpath/xpath');
var fs = require('fs');
var data = fs.readFileSync('/dev/stdin').toString();
try {
    xpath.parse(data);
} catch (e) {
    console.log(e.message);
    process.exit(1);
}
process.exit(0);
