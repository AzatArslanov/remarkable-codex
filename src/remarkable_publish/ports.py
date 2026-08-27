from typing import Protocol

from .domain import LivePublishOutcome, LivePublishRequest


class LivePublisher(Protocol):
    def publish_artifact(self, request: LivePublishRequest) -> LivePublishOutcome: ...
