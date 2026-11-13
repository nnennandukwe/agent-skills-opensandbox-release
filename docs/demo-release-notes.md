This tutorial prerelease contains a small Python demo package and its release
check evidence. GitHub Actions built the wheel, ran the manifest helper in
OpenSandbox, accepted its report, and verified candidate identity before
creating this prerelease. See the linked workflow run for the observed steps.

The example checks manifest structure and package/version agreement with the
built wheel. Teams should add the other tests, approvals, artifact verification,
and deployment requirements their release process needs.
