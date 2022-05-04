.PHONY: requirements upgrade-requirements docs migrations.lock serializer-pickle-files.lock

requirements:
	cd requirements && $(MAKE) requirements

upgrade-requirements:
	cd requirements && $(MAKE) upgrade-requirements

docs:
	cd docs && $(MAKE) html; cd -

serializer-pickle-files.lock:
	./scripts/make-serializer-pickle-files
