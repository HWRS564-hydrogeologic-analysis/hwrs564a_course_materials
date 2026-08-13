FROM mcr.microsoft.com/devcontainers/python:3.11

# Use Astral's official image as the source of the uv executables. Pinning the
# version makes Codespace rebuilds predictable; postbuild.sh retains a fallback
# installer in case this layer is ever bypassed by another container runtime.
COPY --from=ghcr.io/astral-sh/uv:0.11.32 /uv /uvx /usr/local/bin/
