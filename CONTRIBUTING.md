# Contributing

Changes here follow the project's guide, [Contributing to Porelo](https://porelo-ai.github.io/porelo-project/contributing/):
how a change starts as a GitHub issue, what a commit carries, and what a change must satisfy. The
rules are kept there and in the shared block of [`AGENTS.md`](AGENTS.md), not here.

## In this repository

The collection's shape is planned in
[porelo-project's issues](https://github.com/porelo-ai/porelo-project/blob/main/issues/README.md); a change
starts there or as an issue in [`issues/`](issues/README.md).

A change is checked as the Build checks it. The Ansible tools run from the image `build/tools-image` pins, through
podman, so nothing but podman and Java 25 is installed:

    build/tools.sh yamllint --strict -c build/yamllint-ansible.yml .
    build/tools.sh yamllint --strict -c build/yamllint.yml .
    build/tools.sh ansible-lint -c build/ansible-lint.yml
    build/tools.sh ansible-galaxy collection build --output-path target --force
    build/check-tarball.sh target/porelo-host-*.tar.gz

The documents' checks take the shared build tools by `build/pom.xml`:

    ./mvnw -B -q -f build/pom.xml dependency:build-classpath -Dmdep.outputFile=target/tools-cp.txt
    java -cp "$(cat target/tools-cp.txt)" org.fuin.porelo.release.Main check-shared AGENTS.md .editorconfig

and the same for `check-citations .`, `check-doc-site doc mkdocs.yml` and `check-actions .github`.
