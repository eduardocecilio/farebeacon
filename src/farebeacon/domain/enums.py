from enum import StrEnum


class TripType(StrEnum):
    ONE_WAY = "one_way"
    ROUND_TRIP = "round_trip"


class RunTrigger(StrEnum):
    MANUAL = "manual"
    SCHEDULED = "scheduled"


class RunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    PARTIALLY_SUCCEEDED = "partially_succeeded"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class SourceRunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class SourceKind(StrEnum):
    API = "api"
    HTTP_SCRAPER = "http_scraper"
    BROWSER_AUTOMATION = "browser_automation"
    EXTERNAL = "external"
    MOCK = "mock"


class SourceStatus(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"


class AlertEventStatus(StrEnum):
    PENDING = "pending"
    SENDING = "sending"
    SENT = "sent"
    FAILED = "failed"
    SUPPRESSED = "suppressed"
