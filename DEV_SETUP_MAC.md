# Supplementary Guide for Developers Running CommCare HQ on MacOS


## Prerequisites

- You will need `brew` aka [Homebrew](https://brew.sh) for package management.


- It is highly recommended that you install a python environment manager. Two options are:

  - [pyenv](https://github.com/pyenv/pyenv#installation) (recommended) and `pyenv-virtualenv`

    ```sh
    brew install pyenv pyenv-virtualenv
    ```

    To create a new HQ virtual environment running Python 3.9.11, you can do the following:

    ```sh
    pyenv virtualenv 3.9.11 hq
    ```

    Then to enter the environment:

    ```sh
    pyenv activate hq
    ```

  - [virtualenvwrapper](https://virtualenvwrapper.readthedocs.io/en/latest/#introduction)

    Please note that if you use `virtualenvwrapper`, you also need to install `pip`

    To install `pip`:

    ```sh
    sudo python get-pip.py
    ```
    Then install `virtualenvwrapper` with `pip`:
    ```sh
    sudo python3 -m pip install virtualenvwrapper
    ```

- Java (JDK 8)

  We recommend using `sdkman` as a Java environment manager. `jenv` is also an option, though more involved.

    - Example setup using `sdkman`:

      1. [Install sdkman](https://sdkman.io/install)

      2. List available java versions to file one that matches Java (JDK 8)
         ```sh
         sdk list java
         ```
         Look for Java 8 in the list and install, eg:
         ```sh
         sdk install java 8.0.322-zulu
         ```

    - Example setup using `jenv`:

      1. Download and install [Java SE Development Kit 8][oracle_jdk8] from oracle.com downloads page.
         (requires signing in with an Oracle account to download).
      2. Install `jenv`

          ```sh
          brew install jenv
          ```

      3. Configure your shell (Bash folks use `~/.bashrc` instead of `~/.zshrc` below):

          ```sh
          echo 'export PATH="$HOME/.jenv/bin:$PATH"' >> ~/.zshrc
          echo 'eval "$(jenv init -)"' >> ~/.zshrc
          ```

      4. Add JDK 8 to `jenv`:

          ```sh
          jenv add $(/usr/libexec/java_home -v 1.8)
          ```

      5. Verify `jenv` config:

          ```sh
          jenv doctor
          ```

  [oracle_jdk8]: https://www.oracle.com/java/technologies/javase/javase-jdk8-downloads.html


## Issues Installing `requirements/requirements.txt`

- `psycopg2` will complain

  As of Mac OS 11.x Big Sur, the solution for this is:
  ```sh
  brew install libpq --build-from-source
  export LDFLAGS="-L/opt/homebrew/opt/libpq/lib"
  pip install psycopg2-binary
  ```
  
  Or try: ([reference](https://rogulski.it/blog/install-psycopg2-on-apple-m1/)). Used on Mac OS 12.X Monterey.
    ```sh
    export LDFLAGS="-L/opt/homebrew/opt/openssl@1.1/lib"
    export CPPFLAGS="-I/opt/homebrew/opt/openssl@1.1/include"
  ```

- `pip install xmlsec` gives `ImportError`

  Due to issues with recent versions of `libxmlsec1` (v1.3 and after) `pip install xmlsec` is currently broken.
  This is a workaround. This solution also assumes your `homebrew` version is greater than `4.0.13`*:

1. run `brew unlink libxmlsec1`
2. overwrite the contents of `/opt/homebrew/opt/libxmlsec1/.brew/libxmlsec1.rb` with
    [this formula](https://raw.githubusercontent.com/Homebrew/homebrew-core/7f35e6ede954326a10949891af2dba47bbe1fc17/Formula/libxmlsec1.rb).
3. install that formula (`brew install /opt/homebrew/opt/libxmlsec1/.brew/libxmlsec1.rb`)
4. run `pip install xmlsec`

(*)The path to `libxmlsec1.rb` might differ on older versions of homebrew

If it still won't install, this [answer](https://stackoverflow.com/questions/76005401/cant-install-xmlsec-via-pip)
and [thread](https://github.com/xmlsec/python-xmlsec/issues/254) are good starting points for further diagnosing the issue.


### M1 Issues

- `gevent` may present errors when installing with Python <3.9. For this reason, you should avoid using an older version of Python unless it is required.

- `pynacl` will likely install but may throw an error `symbol not found in flat namespace '_ffi_prep_closure'` when attempting to run, particularly when setting up CommCare-Cloud.

  This can be fixed by installing a version of `pynacl` specific to the system architecture:
  ```sh
  arch -arm64 pip install --upgrade --force-reinstall pynacl
  ```


## Docker

Docker images that will not run on Mac OS (Intel or M1):

- `formplayer` (See section on Running Formplayer Outside of Docker in the [Main Developer Setup Guide](https://github.com/dimagi/commcare-hq/blob/master/DEV_SETUP.md))

Docker images that will not run on Mac OS (as of 11.x Big Sur and above):

- `elasticsearch2`
- `elasticsearch5`

### M1 (OS 11.x and above) Recommended Docker Up Command

```sh
./scripts/docker up -d postgres couch redis zookeeper kafka minio
```

Note: `kafka` will be very cranky on start up. You might have to restart it if you see `kafka` errors.
```sh
./scripts/docker restart kafka
```

### Installing and running Elasticsearch 2.4.6 outside of Docker

First, ensure that you have Java 8 running. `java -version` should output something like `openjdk version "1.8.0_322"`.
Use `sdkman` or `jenv` to manage your local java versions.

Download the `tar` file for [elasticsearch 2.4.6](https://www.elastic.co/downloads/past-releases/elasticsearch-2-4-6)

Un-tar and put the folder somewhere you can find it. Take note of tha path (`pwd`) and add the following to your `~/.zshrc`:

```sh
export PATH="/path/to/elasticsearch-2.4.6/bin:$PATH"
```
NOTE: Make sure that `/path/to` is replaced with the actual path!

After this you can open a new terminal window and run elasticsearch with `elasticsearch`.

#### Install Elasticsearch plugins

Now that you have Elasticsearch running you will need to install the necessary plugins:

1. Install the plugin

    ```shell
    $ plugin install analysis-phonetic
    ```

    (If the `plugin` command is not found you will need to use the full path `<es home>/bin/plugin`).

2. Restart the service

3. Verify the plugin was correctly installed

    ```shell
    $ curl "localhost:9200/_cat/plugins?s=component&h=component,version"
    analysis-phonetic 2.4.6
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
