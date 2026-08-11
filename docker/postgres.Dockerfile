FROM postgres:16.14-alpine3.23@sha256:42b8b8b29c8a4e933d88943e5b03001a78794905cf786e6e7634e9f2abd5a0d3

# The official entrypoint only needs gosu when it starts as root. FareBeacon runs
# PostgreSQL as the postgres user directly, so remove that unnecessary attack surface.
RUN rm /usr/local/bin/gosu

USER postgres
