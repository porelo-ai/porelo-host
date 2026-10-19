# build

What builds and checks the collection; none of it ships. `pom.xml` builds nothing: it names the shared build tools, so
`../mvnw` takes them from Central by version for the documents' checks. `tools-image` pins the Ansible tools' image by
digest, and `tools.sh` runs a tool from it on this checkout, through podman, or directly with `HOST_TOOLS_IN_IMAGE=1`
inside that image, as a Porelo task built from `../porelo.yml` is; `check-tarball.sh` refuses a collection tarball that
holds anything the collection does not ship; `molecule.sh` runs the Molecule scenario on a VM it makes and deletes,
from the cloud image `test-image` pins. `ansible-lint.yml` is ansible-lint's settings; `yamllint-ansible.yml`
holds the collection's Ansible YAML to two spaces and `yamllint.yml` every other YAML file to four, as `.editorconfig`
splits them.
