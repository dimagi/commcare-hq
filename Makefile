.PHONY: requirements upgrade-requirements docs migrations.lock

requirements:
	cd requirements && $(MAKE) requirements

upgrade-requirements:
	cd requirements && $(MAKE) upgrade-requirements

docs:
	cd docs && $(MAKE) html; cd -
