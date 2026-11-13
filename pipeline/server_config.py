"""Create a loopback-only server configuration with an ephemeral test key."""

import argparse
import os
import secrets
from pathlib import Path

EXECD_IMAGE = "opensandbox/execd@sha256:6cf7dba2f21f0b536e100563d841ac58a9f31c2b0a081b7ac76796a24d6f47e2"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--state", type=Path, required=True)
    args = parser.parse_args()
    state = args.state.resolve()
    text = f'''[server]
host = "127.0.0.1"
port = 18082
api_key = "{secrets.token_hex(32)}"

[runtime]
type = "docker"
execd_image = "{EXECD_IMAGE}"

[proxy]
resolve_internal = false

[docker]
network_mode = "bridge"
publish_host = "127.0.0.1"

[store]
type = "sqlite"
path = "{state}"

[log]
level = "WARNING"
'''
    descriptor = os.open(args.output, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(descriptor, "w") as stream:
        stream.write(text)
    print("Created private server configuration; key omitted from output.")


if __name__ == "__main__":
    main()
