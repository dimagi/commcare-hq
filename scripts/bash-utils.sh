
function logmsg {
    # USAGE: logmsg [-n] LEVELNAME [MESSAGE ...]
    #
    # Write a log message to stderr.
    # LEVELNAME  log level name (for colorization). Resulting message will be
    #            colorized (if stderr is a TTY) for common level names.
    #        -n  Do not write a trailing newline (must be *very first* argument)
    local echo_args=( -e )
    if [ "x${1}" == "x-n" ]; then
        shift
        echo_args+=( -n )
    fi
    local script=$(basename "$0")
    local levelname="$1"
    shift
    local msg="$*"
    local ccode=''
    local reset=''
    if [ -t 2 ]; then
        # only define color codes when STDERR is a tty
        local color='0' # default no color
        case "$levelname" in
            DEBUG)
                color='1;35' # magenta
                ;;
            INFO)
                color='1;32' # green
                ;;
            WARNING)
                color='0;33' # gold
                ;;
            ERROR)
                color='1;31' # red
                ;;
        esac
        ccode="\\033[${color}m"
        reset='\033[0m'
    fi
    echo "${echo_args[@]}" "[${script}] ${ccode}${levelname}${reset}: $msg"
}

function func_text {
    # USAGE: func_text FUNC_NAME [FUNC_NAME ...]
    #
    # Write the full definition of function(s) FUNC_NAME to stdout.
    local func_name
    for func_name in "$@"; do
        if ! type "$func_name" 2>&1 | grep -E " is a function$" >/dev/null; then
            logmsg ERROR "$func_name is not a function"
            return 1
        fi
        type "$func_name" | tail -n +2
        echo ''
    done
}

function truthy {
    # USAGE: truthy [false|true|no|yes|off|on|0|1]
    #
    # Return with a success or failure based on whether or not the provided
    # argument is "truthy".
    function _usage {
        logmsg ERROR "USAGE: truthy [false|true|no|yes|off|on|0|1]"
        logmsg ERROR "$*"
    }
    if [ $# -gt 1 ]; then
        _usage "too many arguments: $*"
        exit 1
    fi
    local value="$1"
    if [ -n "$value" ]; then
        if echo "$value" | grep -Ei '^(t(rue)?|y(es)?|on|1)$' >/dev/null; then
            return 0
        elif echo "$value" | grep -Ei '^(f(alse)?|n(o)?|off|0)$' >/dev/null; then
            return 1
        else
            _usage "invalid boolean string: '$value'"
            exit 1
        fi
    else
        # absent == false
        return 1
    fi
}
