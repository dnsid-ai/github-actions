# Self-test target for the container workflow and Trivy's Dockerfile checks.
# CANARY: no USER instruction, so the image runs as root (Trivy DS-0002).
FROM alpine:3.22@sha256:5291449c3df73caf6ed85e649dec1b9e818b39a5d8c871e97afc13e9cd5e8fa8
RUN echo "fixture" > /fixture.txt
HEALTHCHECK NONE
CMD ["cat", "/fixture.txt"]
