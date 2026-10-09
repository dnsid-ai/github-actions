package main

import rego.v1

# Every container image must be pinned by digest: a tag can be moved.
deny contains msg if {
	some container in input.spec.template.spec.containers
	not contains(container.image, "@sha256:")
	msg := sprintf("container %q uses image %q without a digest", [container.name, container.image])
}
