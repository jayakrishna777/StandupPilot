"""Shared test doubles for the frozen contracts."""

from standup_pilot.testing.fakes import (
    FakeJiraReader,
    FakeReviewerIdentity,
    InMemoryCaptionStore,
    InMemoryProposalStore,
    StubActionService,
    StubCaptionReceiver,
    StubReviewerAuthorizer,
)

__all__ = [
    "FakeJiraReader",
    "FakeReviewerIdentity",
    "InMemoryCaptionStore",
    "InMemoryProposalStore",
    "StubActionService",
    "StubCaptionReceiver",
    "StubReviewerAuthorizer",
]
