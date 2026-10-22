.POSIX:

help:
	@sh scripts/dev.sh help

doctor:
	@sh scripts/doctor.sh

setup:
	@sh scripts/dev.sh setup

up down status logs dev-api dev-web lint format typecheck test check:
	@sh scripts/dev.sh $@

smoke:
	@sh scripts/smoke-test.sh

.PHONY: help doctor setup up down status logs dev-api dev-web lint format typecheck test check smoke
