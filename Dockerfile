# syntax=docker/dockerfile:1.7@sha256:a57df69d0ea827fb7266491f2813635de6f17269be881f696fbfdf2d83dda33e
FROM python:3.12.11-slim-bookworm@sha256:519591d6871b7bc437060736b9f7456b8731f1499a57e22e6c285135ae657bf7 AS wheel-builder

WORKDIR /build
COPY pyproject.toml requirements-mcp.lock README.md LICENSE ./
COPY src ./src
RUN python -m pip wheel --no-cache-dir --wheel-dir /wheels \
        --constraint requirements-mcp.lock ".[mcp]"

FROM python:3.12.11-slim-bookworm@sha256:519591d6871b7bc437060736b9f7456b8731f1499a57e22e6c285135ae657bf7 AS runtime

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY --from=wheel-builder /wheels /wheels
RUN python -m pip install --no-cache-dir --no-index --find-links=/wheels \
        "remarkable-publish[mcp]==0.3.0" \
    && rm -rf /wheels \
    && useradd --uid 65532 --user-group --no-create-home --shell /usr/sbin/nologin remarkable

USER 65532:65532
WORKDIR /var/lib/remarkable-publish
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HOME=/tmp \
    REMARKABLE_IMAGE_VERSION=0.3.0 \
    REMARKABLE_ARTIFACT_DIR=/artifacts \
    REMARKABLE_STATE_DIR=/var/lib/remarkable-publish

CMD ["remarkable-publish-mcp"]
