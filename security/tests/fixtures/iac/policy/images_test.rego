package main

import rego.v1

test_tag_only_image_denied if {
	count(deny) == 1 with input as {"spec": {"template": {"spec": {"containers": [{"name": "a", "image": "nginx:1.27"}]}}}}
}

test_digest_pinned_image_allowed if {
	count(deny) == 0 with input as {"spec": {"template": {"spec": {"containers": [{"name": "a", "image": "nginx@sha256:0000000000000000000000000000000000000000000000000000000000000000"}]}}}}
}
