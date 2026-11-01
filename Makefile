.POSIX:

help:
	@sh scripts/dev.sh help

doctor:
	@sh scripts/doctor.sh

setup:
	@sh scripts/dev.sh setup

up down status logs health infra-test jev-smoke dev-api dev-web lint lint-backend lint-frontend format format-check format-check-backend typecheck typecheck-backend typecheck-frontend test test-backend test-frontend build-web check:
	@sh scripts/dev.sh $@

security-setup:
	@sh scripts/security-setup.sh

security-check:
	@sh scripts/security-check.sh

security-smoke:
	@sh scripts/security-smoke-test.sh

smoke:
	@sh scripts/smoke-test.sh

setup-api test-api:
	@sh scripts/dev.sh $@

.PHONY: help doctor setup up down status logs health infra-test jev-smoke dev-api dev-web lint lint-backend lint-frontend format format-check format-check-backend typecheck typecheck-backend typecheck-frontend test test-backend test-frontend build-web check security-setup security-check security-smoke smoke setup-api test-api
