CommCare HQ Style
=======

HQStyle is built on top of [our fork](https://github.com/dimagi/hq-bootstrap) of
[Twitter Bootstrap](http://twitter.github.com/bootstrap/) that includes overrides of Twitter Bootstrap styles and
new styles specific to the [CommCare HQ](https://github.com/dimagi/commcare-hq) user interface. This also includes
all the necessary javascript for our bootstrap plugins.

HQStyle is structured as a django app, so that the compiled css and javascript files are easily available to CommCare
HQ and related projects. No compilation of the less files and javascript files is necessary, unless changes are made
to the files in `hqstyle/_less` and `hqstyle/_plugins`.

Requirements for Compiling HQStyle
-------------------------

The following instructions are for *nix users. For windows installation, skip ahead to the bottom of this section.

### nodejs

Both lessc and uglify-js below need nodejs to run. [How to install nodejs](https://github.com/joyent/node/wiki/Installing-Node.js-via-package-manager).

### lessc

The LESS CSS compiler is required to compile all the .less files from hq-boostrap.

Do the following to install `lessc`.

+ `sudo git clone https://github.com/cloudhead/less.js.git /opt/lessc`
+ add `alias lessc='nodejs /opt/lessc/bin/lessc'` to your bash profile

**Note to OSX users:**

Instead of adding the lessc alias, on Mac OS X you should put the lessc executable on the path, e.g. by adding `/opt/lessc/bin/` to the path.

This [LESS app](http://incident57.com/less/) is super useful for working with LESS.
It's highly recommended that you use this when making changes to the .less files. Use this along side the `make extra` command described below for updating changes to javascript or image files.

### uglify-js

Install [npm](http://npmjs.org/).

Then do the following

    npm install uglify-js -g

You may have to run `npm link uglify-js`.

### Installation for Windows Users

Installing the prerequisites on windows is actually quite painless. Install node.js via the latest .msi installer. Then install the dependencies using:

+ npm install less
+ npm install uglify-js

After you're done just update your PATH environment variable to include the bin/ directories containing the lessc and uglifyjs commands.


Compiling HQ Style
------------------

From the root directory of [commcare-hq](https://github.com/dimagi/commcare-hq) run:

    python manage.py make_hqstyle


### Having some aliasing issues?

The following arguments to this management command may help:

+ `direct-lessc` - runs `lessc` directly from `/opt/lessc`

+ `node` - used in addition to `direct-lessc` for when your OSX install of nodejs is for some reason accessed using `node` instead of `nodejs`.

**A note to Devs on OSX**

[Less.app](http://incident57.com/less/index.php) is fantastic for compiling .less files automatically as you make changes. Make sure you set
the correct output paths.
