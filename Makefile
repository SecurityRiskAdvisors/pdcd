message="changes"
# https://python-poetry.org/docs/cli/#version
# 	major	1.3.0	2.0.0
# 	minor	2.1.4	2.2.0
# 	patch	4.1.1	4.1.2
bumprule="patch"

format:
	poetry run black -l 120 pdcd/

.PHONY: dist
dist:
	rm dist/*
	poetry version $(bumprule)
	poetry build -f wheel

git:
	$(eval branch := $(shell git branch --show-current))
	git add .
	git commit -a -m "$(message)"
	git push origin $(branch)

push: format dist git

