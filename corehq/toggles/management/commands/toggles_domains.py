"""
This script is intended to be run in a Django shell, not as a management
command.
"""
from dataclasses import dataclass

from corehq.toggles import NAMESPACE_DOMAIN, StaticToggle, all_toggles_by_name

DOMAINS = """
demo
example
""".split()


@dataclass
class ToggleDomain:
    toggle: StaticToggle
    domains: list[str]


def toggles_enabled_for_domain(domain: str) -> dict[str, StaticToggle]:
    return {
        toggle_name: toggle
        for toggle_name, toggle in all_toggles_by_name().items()
        if toggle.enabled(domain, NAMESPACE_DOMAIN)
    }


def print_toggle_domains(toggle_domains: dict[str, ToggleDomain]):
    for toggle_name, toggle_domain in toggle_domains.items():
        print(f"Toggle: {toggle_name}")
        print(f"  Tag: {toggle_domain.toggle.tag.name}")
        print(f"  Description: {toggle_domain.toggle.description}")
        print(f"  Link: {toggle_domain.toggle.help_link}")
        print(f"  Domains: {', '.join(toggle_domain.domains)}")
        print()


toggle_domains = {}
for domain in DOMAINS:
    for toggle_name, toggle in toggles_enabled_for_domain(domain).items():
        if toggle_name not in toggle_domains:
            toggle_domains[toggle_name] = ToggleDomain(toggle, [])
        toggle_domains[toggle_name].domains.append(domain)


print_toggle_domains(toggle_domains)
