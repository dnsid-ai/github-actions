# DeepSource templates

DeepSource is a GitHub App, not a workflow: it reads `.deepsource.toml` from the
repo root and reviews each PR on its own servers. That is why it isn't one of the
jobs in this repo. To turn it on for a repo:

1. Copy the matching template below to `.deepsource.toml` at the repo root.
2. Activate the repo in the DeepSource dashboard. That needs a DeepSource org admin.

If a repo already has a `.deepsource.toml`, keep it. These templates are for repos
that don't have one yet.

DeepSource and the workflows overlap on purpose. DeepSource comments on the diff in
review; the workflows are the merge gate. Keep both, and treat a finding either
one raises as real.
