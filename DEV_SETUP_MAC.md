# Supplementary Guide for Developers Running CommCare HQ on MacOS


## Prerequisites

- You will need `brew` aka [Homebrew](https://brew.sh) for package management.


- First, install [uv](https://docs.astral.sh/uv/) to manage Python versions and virtualenvs.

  ```sh
  brew install uv
  ```

  To create a new HQ virtual environment, you can do the following:

  ```sh
  uv venv
  ```

  Then to enter the environment:

  ```sh
  source .venv/bin/activate
  ```

- Java (JDK 17)

  We recommend using `sdkman` as a Java environment manager. `jenv` is also an option, though more involved.

    - Example setup using `sdkman`:

        1. [Install sdkman](https://sdkman.io/install)

           On macOS, the default shell (Zsh) and the outdated system Bash can cause the standard installer to fail. Use this command to ensure a compatible installation:

           ```sh
           # Run the installer with Zsh-compatible pattern matching
           curl -s "https://get.sdkman.io" | zsh -o NO_NOMATCH

           # Initialize SDKMAN! in your current session
           source "$HOME/.sdkman/bin/sdkman-init.sh"
           ```

        2. List available java versions to file one that matches Java (JDK 17)
           ```sh
           sdk list java | grep 17
           ```
           Look for Java 17 in the list and install, eg:
           ```sh
           sdk install java 17.0.8-zulu
           ```

    - Example setup using `jenv`:

        1. Download and install [Java SE Development Kit 17][oracle_jdk17] from oracle.com downloads page.

        2. Install `jenv`

            ```sh
            brew install jenv
            ```

        3. Configure your shell (Bash folks use `~/.bashrc` instead of `~/.zshrc` below):

            ```sh
            echo 'export PATH="$HOME/.jenv/bin:$PATH"' >> ~/.zshrc
            echo 'eval "$(jenv init -)"' >> ~/.zshrc
            ```

        4. Add JDK 17 to `jenv`:

            ```sh
            jenv add $(/usr/libexec/java_home)
            ```

        5. Verify `jenv` config:

            ```sh
            jenv doctor
            ```

  [oracle_jdk17]: https://www.oracle.com/java/technologies/javase/jdk17-archive-downloads.html

## Dart Sass

`npm install -g sass` (see [Step 8 in the Main Developer Setup
Guide](https://github.com/dimagi/commcare-hq/blob/master/DEV_SETUP.md#step-8-configure-css-precompilers-2-options))
is the simplest option and needs nothing extra. Homebrew provides the faster native binary,
but the formula lives in a third-party tap and declares a build dependency on another one,
so both must be trusted first:

```sh
brew tap dart-lang/dart
brew trust dart-lang/dart   # Homebrew refuses to load formulae from untrusted taps
brew install sass/sass/sass
```

Only do this if you are comfortable trusting those taps. Without the `brew trust` step the
install fails with `Refusing to load formula dart-lang/dart/dart from untrusted tap` — and it
exits 0 having installed nothing, so confirm with `command -v sass`.


## Issues With `uv sync`

- `psycopg2` may complain

  As of Mac OS 11.x Big Sur, the solution for this is:
  ```sh
  brew install libpq --build-from-source
  export LDFLAGS="-L/opt/homebrew/opt/libpq/lib"
  uv pip install psycopg2-binary
  ```
  
  Or try: ([reference](https://rogulski.it/blog/install-psycopg2-on-apple-m1/)). Used on Mac OS 12.X Monterey.
    ```sh
    export LDFLAGS="-L/opt/homebrew/opt/openssl@1.1/lib"
    export CPPFLAGS="-I/opt/homebrew/opt/openssl@1.1/include"
  ```

- `uv pip install xmlsec` gives `ImportError`

  This is no longer expected — `uv sync` installs a prebuilt `xmlsec` wheel that needs none of
  the steps below. Only reach for this if you actually hit the `ImportError`.

  Due to issues with recent versions of `libxmlsec1` (v1.3 and after) `uv pip install xmlsec` may be broken.
  This is a workaround. This solution also assumes your `homebrew` version is greater than `4.0.13`*:

1. run `brew unlink libxmlsec1`
2. overwrite the contents of `/opt/homebrew/opt/libxmlsec1/.brew/libxmlsec1.rb` with
    [this formula](https://raw.githubusercontent.com/Homebrew/homebrew-core/7f35e6ede954326a10949891af2dba47bbe1fc17/Formula/libxmlsec1.rb).
3. install that formula (`brew install /opt/homebrew/opt/libxmlsec1/.brew/libxmlsec1.rb`)
4. run `uv pip install xmlsec`

(*)The path to `libxmlsec1.rb` might differ on older versions of homebrew

If it still won't install, this [answer](https://stackoverflow.com/questions/76005401/cant-install-xmlsec-via-pip)
and [thread](https://github.com/xmlsec/python-xmlsec/issues/254) are good starting points for further diagnosing the issue.


### M1 Issues

- `pynacl` will likely install but may throw an error `symbol not found in flat namespace '_ffi_prep_closure'` when attempting to run, particularly when setting up CommCare-Cloud.

  This can be fixed by installing a version of `pynacl` specific to the system architecture:
  ```sh
  arch -arm64 uv pip install --upgrade --force-reinstall pynacl
  ```


## Docker

### Container engines

macOS cannot run Linux containers directly, so you need an engine that provides a
Docker-compatible daemon in a VM. Any of these work for HQ's services:

| Engine | Notes |
| --- | --- |
| [Docker Desktop](https://docs.docker.com/desktop/install/mac-install/) | GUI app. Bundles `docker compose`. Requires a paid subscription for larger organizations, so check whether yours is covered. |
| [Colima](https://github.com/abiosoft/colima) | CLI only, no licensing question. Needs `docker compose` installed and registered separately (below). |
| [OrbStack](https://orbstack.dev/) | Fast on Apple Silicon. Bundles `docker compose`. Free for personal use, paid for commercial. |

Whichever you pick, `docker` on its own is only the client — it needs one of the above behind
it, or every command fails with `Cannot connect to the Docker daemon`.

#### Colima

```sh
brew install colima docker docker-compose
colima start --cpu 4 --memory 8 --disk 60 --vm-type vz --vz-rosetta
```

`--vm-type vz --vz-rosetta` enables Rosetta translation, which matters because two of HQ's
images are amd64-only (see [Image architectures](#image-architectures)).

Homebrew's `docker-compose` is not automatically visible to the Docker CLI, so `docker
compose` (and therefore `./scripts/docker`) will not resolve until you point the CLI at it.
Add the plugin directory to `~/.docker/config.json`, merging with whatever is already in
that file:

```json
{
  "cliPluginsExtraDirs": ["/opt/homebrew/lib/docker/cli-plugins"]
}
```

That path is for Apple Silicon; on Intel it is `/usr/local/lib/docker/cli-plugins`. JSON has
no shell expansion, so the literal path is required — `brew --prefix` prints yours. Verify
with `docker compose version`.

### Image architectures

Docker images that will not run on Mac OS (Intel or M1):

- `formplayer` (See section on Running Formplayer Outside of Docker in the [Main Developer Setup Guide](https://github.com/dimagi/commcare-hq/blob/master/DEV_SETUP.md))

Images published only for `amd64`, which therefore run emulated on Apple Silicon:

- `elasticsearch6`
- `postgres` (`dimagi/docker-postgresql`)

Emulation makes these noticeably slower but they do work. Rosetta translation is much
faster than QEMU, so enable it if your container engine supports it — with Colima that
means `colima start --vm-type vz --vz-rosetta`.

### M1 (OS 11.x and above) Recommended Docker Up Command

```sh
./scripts/docker up -d postgres couch redis elasticsearch6 zookeeper kafka minio
```

Note: `kafka` will be very cranky on start up. You might have to restart it if you see `kafka` errors.
```sh
./scripts/docker restart kafka
```

### Installing and running Elasticsearch 6.8.23 outside of Docker

You should not need this — `elasticsearch6` runs fine in Docker on Apple Silicon. Keep it as
a fallback if the container gives you trouble, or if you want to avoid the emulation
overhead.

First, ensure that you have Java 17 running. `java -version` should output something like `openjdk version "17.0.7" 2023-04-18 LTS"`.
Use `sdkman` or `jenv` to manage your local java versions.

Download the `tar` file for elasticsearch 6.8.23

```sh
curl https://artifacts.elastic.co/downloads/elasticsearch/elasticsearch-6.8.23.tar.gz --output elasticsearch-6.8.23.tar.gz
```

Un-tar it and put the folder somewhere you can find it:

```sh
tar -xvzf elasticsearch-6.8.23.tar.gz
```

Take note of that path (`pwd`), then add the following to your `~/.zshrc`:

```sh
export PATH="/path/to/elasticsearch-6.8.23/bin:$PATH"
```
NOTE: Make sure that `/path/to` is replaced with the actual path!

You would need to update couple of setting in order to make elasticsearch run on your mac.

Change into elasticsearch directory

```sh
cd /path/to/elasticsearch-6.8.23
```

- In `config/jvm.options`, comment out `10-:-XX:UseAVX=2`

```sh
sed -i '' '/10-:-XX:UseAVX=2/ s/^/# /' config/jvm.options
```

- In `config/elasticsearch.yml`, add xpack.ml.enabled: false

```sh
echo "xpack.ml.enabled: false" >> config/elasticsearch.yml
```

After this you can open a new terminal window and run elasticsearch with `elasticsearch`.


#### Install Elasticsearch plugins

Now that you have Elasticsearch running you will need to install the necessary plugins:

1. Install the plugin

    ```sh
    elasticsearch-plugin install analysis-phonetic
    ```

    (If the `plugin` command is not found you will need to use the full path `<es home>/bin/plugin`).

2. Restart the service

3. Verify the plugin was correctly installed

    ```sh
    curl "localhost:9200/_cat/plugins?s=component&h=component,version"
    > analysis-phonetic 6.8.23
    ```


## Refreshing data in `elasticsearch` manually (alternative to `run_ptop`)

FYI, be sure to check out the [FAQ on elasticsearch](https://github.com/dimagi/commcare-hq/blob/master/DEV_FAQ.md#elasticsearch).

To refresh specific indices in elasticsearch you can do the following...

First make sure everything is up-to-date
```sh
./manage.py ptop_preindex --reset

./manage.py preindex_everything
```

Force a re-index of `forms` and `cases`:
```sh
./manage.py ptop_reindexer_v2 sql-case --reset
./manage.py ptop_reindexer_v2 sql-form --reset
```

For other indices see `./manage.py ptop_reindexer_v2 --help`
