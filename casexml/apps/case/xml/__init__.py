
V1 = "1.0"
V2 = "2.0"
DEFAULT_VERSION = V1
LEGAL_VERSIONS = [V1, V2]

def check_version(version):
    if not version in LEGAL_VERSIONS:
        raise ValueError("%s is not a legal version, must be one of: %s" % \
                         (version, ", ".join(LEGAL_VERSIONS)))
    
