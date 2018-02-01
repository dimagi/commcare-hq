from corehq import toggles, feature_previews


def get_toggles_previews(domain):
    return {
        'toggles': list(toggles.toggles_dict(domain=domain)),
        'previews': list(feature_previews.previews_dict(domain=domain))
    }
