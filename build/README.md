# build

What builds and checks the collection; none of it ships. `pom.xml` builds nothing: it names the shared build tools, so
`../mvnw` takes them from Central by version for the documents' checks. `tools-image` pins the Ansible tools' image by
digest, and `tools.sh` runs a tool from it on this checkout, through podman, or directly with `HOST_TOOLS_IN_IMAGE=1`
inside that image, as a Porelo task built from `../porelo.yml` is; `check-tarball.sh` refuses a collection tarball that
holds anything the collection does not ship; `molecule.sh` runs the Molecule scenario on a VM it makes and deletes,
from the cloud image `test-image` pins. `sanity.sh` runs `ansible-test sanity` offline on a copy of the
collection, in an image `sanity/Containerfile` builds on the tools image with the wheels `sanity/requirements.txt`
takes by hash. `ansible-lint.yml` is ansible-lint's settings; `yamllint-ansible.yml`
holds the collection's Ansible YAML to two spaces and `yamllint.yml` every other YAML file to four, as `.editorconfig`
splits them.

`porelo-vm` is the development VM tool shared by `molecule.sh` and `rehearse-move.sh`. It stays in `build/`, outside
the collection tarball, and no host role installs it. The pool VM's give-back script remains in its role.

`stage-packages.sh` requires `PORELO_HOST_DEB`, stages it with `PORELO_HOST_PACKAGES`, rejects conflicting package
identities and records exact versions and checksums. Molecule and the move rehearsal copy this set before the first
up; remote package directories are keyed by its manifest to prevent old artifacts from being reused.
