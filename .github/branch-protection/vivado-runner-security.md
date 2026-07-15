# Vivado Trusted Runner Security Contract

The `vivado-trusted-runner` environment protects a licensed self-hosted Windows
runner. Repository administrators must configure required reviewers for this
environment; repository workflow text cannot enforce that external setting.

The workflow rejects fork pull requests and accepts only `OWNER`, `MEMBER`, or
`COLLABORATOR` authors after the `vivado-integration` label is applied. Checkout
must keep `persist-credentials: false` and `clean: true`.

The runner should be ephemeral. If an ephemeral runner cannot be provisioned,
the operator must restore a clean workspace and remove generated credentials,
tool configuration, and build outputs between jobs. The runner must not host
unrelated services or retain repository tokens after a job finishes.
