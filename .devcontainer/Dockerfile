FROM mcr.microsoft.com/devcontainers/python:3.11

# Install system utilities useful for package inspection
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    jq \
    file \
    binutils \
    xxd \
    && rm -rf /var/lib/apt/lists/*
