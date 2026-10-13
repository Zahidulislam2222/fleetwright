"""The single typed configuration boundary for every Fleetwright service (Rule 12).

Every environment-dependent value is read here from `FW_*` environment variables (nested groups use
`__`, e.g. `FW_DB__APP_DSN`). Business modules receive these objects; they never read the
environment or invent fallbacks themselves. Maintained product data (demo catalogue, filters,
provider profiles) lives in YAML under `config/` and is loaded by `fw_core.data`.

Defaults below are only the safe, non-secret, environment-independent ones (timeouts, sizes,
ratios). Anything that names a host, port, path or secret has no default and must be configured.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseModel):
    """One Postgres connection pool. Each service gets only the role it needs:
    fw_app (API + control loops), fw_worker (narrow grants), fw_owner (migrations/seeding only),
    fw_board (the mock board's own database). RLS applies to fw_app and fw_worker."""

    dsn: SecretStr
    pool_size: int = Field(default=10, ge=1, le=200)
    pool_max_overflow: int = Field(default=5, ge=0, le=200)
    pool_timeout_s: float = Field(default=5.0, gt=0)
    statement_timeout_ms: int = Field(default=5000, ge=100)


class RedisSettings(BaseModel):
    """`core` carries live-update pub/sub and rate limits; each cell has its own Redis for streams."""

    core_url: SecretStr
    cells: dict[str, SecretStr]  # cell id -> redis URL (JSON in env)
    socket_timeout_s: float = Field(default=2.0, gt=0)

    @field_validator("cells")
    @classmethod
    def _non_empty(cls, v: dict[str, SecretStr]) -> dict[str, SecretStr]:
        if not v:
            raise ValueError("at least one cell Redis must be configured")
        return v


class BoardClientSettings(BaseModel):
    """How Fleetwright services reach the mock board."""

    internal_url: str  # how workers and the coordinator reach the board
    public_url: str  # what browsers outside the server use (links in the dashboard)
    admin_token: SecretStr  # the board's admin API (adversity toggles, ground truth)
    timeout_s: float = Field(default=10.0, gt=0)


class BoardSettings(BaseModel):
    """The fictitious mock load board itself (Phase 2 test target)."""

    admin_token: SecretStr  # protects the board's adversity / ground-truth admin API
    cookie_secure: bool = True
    session_ttl_s: int = Field(default=1800, ge=30)
    otp_ttl_s: int = Field(default=300, ge=30)
    otp_length: int = Field(default=6, ge=4, le=10)
    email_domain: str  # demo carrier mailboxes, e.g. board.demo.test (reserved TLD)
    smtp_host: str
    smtp_port: int = Field(ge=1, le=65535)
    mail_from: str
    feed_rate_per_min: float = Field(default=6.0, ge=0)  # starting rate; changed live by the admin API
    feed_rate_max_per_min: float = Field(default=6000.0, ge=0)  # 100/s ceiling for stress runs
    feed_poll_ms: int = Field(default=500, ge=50)  # how often the board page asks for new loads
    load_visible_s: int = Field(default=900, ge=10)  # loads older than this drop off the feed
    feed_page_limit: int = Field(default=200, ge=1, le=1000)


class MailpitSettings(BaseModel):
    api_url: str  # Mailpit HTTP API, used by the email OTP adapter


class VaultSettings(BaseModel):
    """Envelope encryption: a per-record data key, wrapped by this master key (KMS on AWS later)."""

    master_key_b64: SecretStr  # 32 random bytes, base64
    key_id: str = "local-1"


class ClaimSettings(BaseModel):
    lease_ttl_ms: int = Field(default=8000, ge=200)
    queued_max_age_s: int = Field(default=120, ge=1)  # a job not leased by then is expired
    fast_lock_ttl_ms: int = Field(default=30000, ge=100)
    stream_maxlen: int = Field(default=100_000, ge=100)
    max_deliveries: int = Field(default=5, ge=1)  # then the message goes to the dead-letter stream
    autoclaim_idle_ms: int = Field(default=5000, ge=100)
    outbox_poll_ms: int = Field(default=250, ge=10)
    detection_retry_s: float = Field(default=5.0, ge=0.1)
    outbox_batch: int = Field(default=200, ge=1, le=5000)
    reconcile_interval_s: float = Field(default=2.0, gt=0)
    filter_reload_s: float = Field(default=30.0, gt=0)  # safety net; pub/sub reload is immediate


class ControlSettings(BaseModel):
    """Per-cell control loops: dispatcher, outbox relay, reconciler."""

    cell: str
    tenant_refresh_s: float = Field(default=2.0, gt=0)  # how fast a tenant move is noticed
    read_block_ms: int = Field(default=500, ge=10)
    read_count: int = Field(default=200, ge=1)
    unknown_grace_ms: int = Field(default=2000, ge=0)  # let a slow actor answer before checking the target
    seen_ttl_s: int = Field(default=600, ge=1)  # fast-path duplicate window for detections


class WorkerSettings(BaseModel):
    cell: str
    reserved_account_groups: tuple[str, ...] = ()  # named pools dedicated to approved workflows
    contexts: int = Field(default=4, ge=1, le=200)
    watchers: int = Field(default=1, ge=0, le=50)
    detection_batch: int = Field(default=100, ge=1, le=1000)
    headless: bool = True
    action_mode: Literal["http", "click"] = "http"
    heartbeat_s: float = Field(default=2.0, gt=0)
    heartbeat_ttl_s: float = Field(default=10.0, gt=0)
    recycle_after_actions: int = Field(default=500, ge=1)
    session_refresh_share: float = Field(default=0.7, gt=0, lt=1)  # refresh at 70% of the TTL
    action_timeout_ms: int = Field(default=5000, ge=100)
    login_timeout_ms: int = Field(default=20000, ge=1000)
    otp_wait_s: float = Field(default=30.0, gt=0)
    otp_clock_margin_s: float = Field(default=2.0, ge=0)  # mail-server clocks lag behind the worker
    account_hold_s: float = Field(default=15.0, gt=0)  # account mutex lease, renewed on every heartbeat
    restart_backoff_s: float = Field(default=5.0, gt=0)  # wait before retrying a slot that failed
    evidence_on_failure: bool = True
    drain_timeout_s: float = Field(default=20.0, gt=0)


class StorageSettings(BaseModel):
    backend: Literal["local"] = "local"
    local_dir: Path
    retention_days: int = Field(default=7, ge=1)


class AuthSettings(BaseModel):
    cookie_name: str = "fw_session"
    mfa_cookie_name: str = "fw_mfa"  # short-lived, between the password and the code step
    csrf_header: str = "X-CSRF-Token"  # mutations must echo the session's CSRF token here
    cookie_secure: bool = True
    session_ttl_s: int = Field(default=8 * 3600, ge=60)
    mfa_pending_ttl_s: int = Field(default=300, ge=30)
    login_max_attempts: int = Field(default=5, ge=1)
    login_window_s: int = Field(default=900, ge=10)
    lockout_s: int = Field(default=900, ge=10)
    # Every password attempt (right or wrong) per client address range within login_window_s; the
    # demo password is public, so failures alone cannot bound the hashing work one client causes.
    password_attempts_per_window: int = Field(default=30, ge=1)
    # argon2 verifies at once (each holds ~64 MiB and a CPU core); the rest wait their turn.
    hash_concurrency: int = Field(default=2, ge=1)
    totp_issuer: str = "Fleetwright"
    totp_valid_window: int = Field(default=1, ge=0, le=2)


class DemoSettings(BaseModel):
    """Public demo behaviour. Caps are enforced server-side, whatever the browser sends."""

    tenant_slug: str = "demo"
    public_read: bool = False  # anonymous visitors get a read-only view of the demo tenant
    show_demo_mfa_code: bool = False  # demo account only: the login page shows its live TOTP code
    run_max_minutes: int = Field(default=5, ge=1, le=60)
    run_max_rate_per_min: float = Field(default=120.0, gt=0)
    # The shared demo login. Its password and live MFA code are deliberately shown on the login
    # page (show_demo_mfa_code); the account can only use demo controls, capped by config/demo.yaml.
    account_email: str = "demo@fleetwright.demo"
    account_password: SecretStr | None = None  # unset: no demo login
    reset_after_s: int = Field(default=900, ge=60)  # demo settings revert after this long
    reset_check_s: float = Field(default=15.0, gt=0)  # how often the reset loop looks


class ApiSettings(BaseModel):
    host: str  # bind address of `python -m fw_coordinator.api`
    port: int = Field(ge=1, le=65535)
    page_size_default: int = Field(default=25, ge=1)
    page_size_max: int = Field(default=200, ge=1)
    trusted_proxy_hops: int = Field(default=1, ge=0)  # for client IP (rate limits, audit)
    worker_stale_after_s: float = Field(default=10.0, gt=0)  # no heartbeat for this long: stale
    worker_dead_after_s: float = Field(default=60.0, gt=0)
    worker_recent_s: float = Field(default=3600.0, gt=0)  # stopped workers older than this are not listed
    series_minutes: int = Field(default=60, ge=5, le=1440)  # overview chart window
    latency_window_s: int = Field(default=3600, ge=60)


class GatewaySettings(BaseModel):
    host: str  # bind address of `python -m fw_gateway`
    port: int = Field(ge=1, le=65535)
    keepalive_s: float = Field(default=15.0, gt=0)
    max_clients: int = Field(default=2000, ge=1)
    client_queue: int = Field(default=200, ge=1)  # per-client backlog before it is dropped
    revocation_check_s: float = Field(default=1.0, gt=0)


class WorkflowSettings(BaseModel):
    lease_s: float = Field(default=90.0, gt=0)
    approval_ttl_s: int = Field(default=300, ge=1)
    grant_ttl_s: int = Field(default=3600, ge=1)
    poll_s: float = Field(default=1.0, gt=0)
    evidence_page_size: int = Field(default=100, ge=1, le=1000)
    action_timeout_ms: int = Field(default=10000, ge=100)
    reconcile_grace_s: float = Field(default=10.0, ge=0)
    alert_unknown_after_s: float = Field(default=300.0, gt=0)
    response_max_bytes: int = Field(default=65536, ge=1024)
    lease_margin_s: float = Field(default=5.0, gt=0)
    tenant_batch: int = Field(default=32, ge=1, le=256)
    jobs_per_tenant: int = Field(default=1, ge=1, le=16)
    drain_timeout_s: float = Field(default=20, gt=0)

    @model_validator(mode="after")
    def execution_fits_lease(self) -> WorkflowSettings:
        if self.lease_s <= self.action_timeout_ms / 1000 + self.lease_margin_s:
            raise ValueError("lease must exceed the bounded action phase plus safety margin")
        return self


class McpSettings(BaseModel):
    tenant_id: str
    access_token: SecretStr


class BackupSettings(BaseModel):
    directory: Path
    container: str
    executable: str
    username: str
    databases: list[str] = Field(min_length=1)
    timeout_s: float = Field(default=120.0, gt=0)
    interval_s: float = Field(default=86400.0, gt=0)
    retention_count: int = Field(default=7, ge=1)

    @field_validator("databases")
    @classmethod
    def safe_identifiers(cls, values: list[str]) -> list[str]:
        if any(not name.replace("_", "").isalnum() or not name[0].isalpha() for name in values):
            raise ValueError("database names must be safe identifiers")
        return values


class ProbeSettings(BaseModel):
    model_config = {"extra": "forbid"}
    name: str = Field(pattern="^[a-z][a-z0-9_-]{0,63}$")
    url: str
    expected_status: int = Field(default=200, ge=100, le=599)
    bearer_token: SecretStr | None = None
    tenant_id: str | None = None


class MonitorSettings(BaseModel):
    database: Path
    probes: list[ProbeSettings] = Field(min_length=1, max_length=20)
    interval_s: float = Field(default=60, ge=1)
    timeout_s: float = Field(default=10, gt=0, le=60)
    failures_before_alert: int = Field(default=3, ge=1)
    response_max_bytes: int = Field(default=65536, ge=1024)
    retention_days: int = Field(default=30, ge=1)
    backup_directory: Path | None = None
    backup_max_age_s: float = Field(default=172800, gt=0)
    notification_file: Path
    notification_limit: int = Field(default=200, ge=1, le=10000)

    @model_validator(mode="after")
    def unique_probes(self) -> MonitorSettings:
        if len({p.name for p in self.probes}) != len(self.probes):
            raise ValueError("monitor probe names must be unique")
        return self


class MonitorGrantSettings(BaseModel):
    tenant_id: UUID
    user_id: UUID
    token_file: Path
    authority_command: list[str] | None = None
    ttl_s: int = Field(default=3600, ge=60)
    renewal_margin_s: float = Field(default=300, gt=0)

    @model_validator(mode="after")
    def bounded_renewal(self) -> MonitorGrantSettings:
        if self.renewal_margin_s >= self.ttl_s:
            raise ValueError("grant renewal margin must be below its lifetime")
        return self


class RecoverySettings(BaseModel):
    directory: Path
    master_key_b64: SecretStr
    key_id: str
    max_archive_bytes: int = Field(default=268435456, ge=1024)
    retention_count: int = Field(default=7, ge=2)


class ReleaseSigningSettings(BaseModel):
    private_key_file: Path
    public_key_file: Path
    key_id: str


class CrawlSettings(BaseModel):
    output_directory: Path
    cell: str
    timeout_s: float = Field(default=5, gt=0)
    request_budget_s: float = Field(default=10, gt=0)
    lease_s: float = Field(default=60, gt=0)
    poll_s: float = Field(default=2, gt=0)
    domain_delay_s: float = Field(default=1, ge=0)
    max_pages: int = Field(default=100, ge=1, le=10000)
    max_items_per_page: int = Field(default=1000, ge=1, le=10000)
    max_response_bytes: int = Field(default=2097152, ge=1024)
    max_attempts: int = Field(default=3, ge=1, le=10)
    retry_base_s: float = Field(default=2, gt=0)
    retry_jitter_s: float = Field(default=1, ge=0)
    tenant_batch: int = Field(default=100, ge=1, le=10000)
    retention_batch: int = Field(default=100, ge=1, le=10000)
    retention_days: int = Field(default=7, ge=1)
    drop_alert_share: float = Field(default=0.5, gt=0, lt=1)
    user_agent: str = "FleetwrightCrawler"
    owned_origin_private_access: bool = False
    origins: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def request_fits_lease(self) -> CrawlSettings:
        if self.timeout_s > self.request_budget_s:
            raise ValueError("socket timeout must fit the total request budget")
        if self.lease_s <= self.request_budget_s * 2 + self.poll_s:
            raise ValueError("crawl lease must exceed both bounded requests plus polling margin")
        return self


class AgentSettings(BaseModel):
    database: Path
    profile_directory: Path
    evidence_directory: Path
    model_url: str
    model_id: str
    host: str
    port: int = Field(ge=1, le=65535)
    allowed_origins: list[str] = Field(min_length=1, max_length=20)
    cdp_url: str | None = None
    headless: bool = True
    model_timeout_s: float = Field(default=120, gt=0)
    model_max_bytes: int = Field(default=65536, ge=1024)
    model_max_tokens: int = Field(default=512, ge=1, le=8192)
    model_keep_alive_s: int = Field(default=0, ge=0, le=3600)
    task_timeout_s: float = Field(default=180, gt=0)
    action_timeout_ms: int = Field(default=10000, ge=100)
    max_tabs: int = Field(default=3, ge=1, le=20)
    max_actions: int = Field(default=12, ge=1, le=100)
    approval_ttl_s: int = Field(default=300, ge=1)
    max_content_chars: int = Field(default=2000, ge=1, le=20000)
    max_request_bytes: int = Field(default=16384, ge=1024)
    max_requests: int = Field(default=100, ge=1, le=10000)
    history_limit: int = Field(default=100, ge=1, le=10000)
    lab_enabled: bool = True


class _Base(BaseSettings):
    # extra="ignore": one local .env serves every service; each service reads only its groups.
    # tests/test_settings.py checks .env.example against all service classes, so typos still fail.
    model_config = SettingsConfigDict(env_prefix="FW_", env_nested_delimiter="__", extra="ignore")

    environment: Literal["local", "test", "vps", "aws"]
    config_dir: Path  # YAML product data (demo catalogue, filters, provider profiles)
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"


class BoardAppSettings(_Base):
    """Mock board process. Holds no Fleetwright secret."""

    board: BoardSettings
    board_db: DatabaseSettings


class CoordinatorSettings(_Base):
    """The console's `/v1` API (`fw_coordinator.api`)."""

    app_db: DatabaseSettings
    redis: RedisSettings
    board_client: BoardClientSettings
    vault: VaultSettings
    auth: AuthSettings = AuthSettings()
    demo: DemoSettings = DemoSettings()
    api: ApiSettings
    workflows: WorkflowSettings = WorkflowSettings()
    crawl: CrawlSettings


class SeedSettings(BaseModel):
    """`python -m fw_coordinator.seed`: the demo tenant, its owner, the shared demo login and the
    demo board accounts. Idempotent; secrets come from env (generated by tools/dev/make_env.py)."""

    cell: str
    owner_email: str
    owner_name: str = "Owner"
    owner_password: SecretStr
    owner_totp_b32: SecretStr  # base32 TOTP secret, also added to the owner's authenticator app


class SeedAppSettings(_Base):
    app_db: DatabaseSettings
    vault: VaultSettings
    board_client: BoardClientSettings
    demo: DemoSettings = DemoSettings()
    seed: SeedSettings


class ControlAppSettings(_Base):
    app_db: DatabaseSettings
    redis: RedisSettings
    board_client: BoardClientSettings
    vault: VaultSettings
    claims: ClaimSettings = ClaimSettings()
    control: ControlSettings


class MigrationSettings(_Base):
    """Schema migrations and seeding (role fw_owner); never used by a long-running service."""

    owner_db: DatabaseSettings
    vault: VaultSettings
    board_client: BoardClientSettings


class GatewayAppSettings(_Base):
    app_db: DatabaseSettings
    redis: RedisSettings
    auth: AuthSettings = AuthSettings()
    demo: DemoSettings = DemoSettings()
    gateway: GatewaySettings


class WorkerAppSettings(_Base):
    worker_db: DatabaseSettings
    redis: RedisSettings
    board_client: BoardClientSettings
    mailpit: MailpitSettings
    vault: VaultSettings
    claims: ClaimSettings = ClaimSettings()
    worker: WorkerSettings
    storage: StorageSettings


class WorkflowAppSettings(_Base):
    app_db: DatabaseSettings
    board_client: BoardClientSettings
    vault: VaultSettings
    mailpit: MailpitSettings
    worker: WorkerSettings
    workflows: WorkflowSettings = WorkflowSettings()


class McpAppSettings(_Base):
    app_db: DatabaseSettings
    mcp: McpSettings
    workflows: WorkflowSettings = WorkflowSettings()


class BackupAppSettings(_Base):
    backup: BackupSettings


class MonitorAppSettings(_Base):
    monitor: MonitorSettings
    app_db: DatabaseSettings | None = None
    monitor_grant: MonitorGrantSettings | None = None

    @model_validator(mode="after")
    def paired_authority(self) -> MonitorAppSettings:
        if self.monitor_grant is not None and self.app_db is None and not self.monitor_grant.authority_command:
            raise ValueError("monitor grant renewal requires database authority")
        return self


class MonitorAuthorityAppSettings(_Base):
    app_db: DatabaseSettings


class RecoveryAppSettings(_Base):
    recovery: RecoverySettings


class ReleaseSigningAppSettings(_Base):
    release_signing: ReleaseSigningSettings


class CrawlAppSettings(_Base):
    app_db: DatabaseSettings
    board_client: BoardClientSettings
    crawl: CrawlSettings


class AgentAppSettings(_Base):
    agent: AgentSettings


SERVICE_SETTINGS: tuple[type[_Base], ...] = (
    BoardAppSettings,
    CoordinatorSettings,
    ControlAppSettings,
    SeedAppSettings,
    MigrationSettings,
    GatewayAppSettings,
    WorkerAppSettings,
    WorkflowAppSettings,
    McpAppSettings,
    BackupAppSettings,
    MonitorAppSettings,
    MonitorAuthorityAppSettings,
    RecoveryAppSettings,
    ReleaseSigningAppSettings,
    CrawlAppSettings,
    AgentAppSettings,
)


def load[S: _Base](cls: type[S]) -> S:
    """Read one service's settings from the environment (and `.env` in the working directory)."""
    return cls(_env_file=_env_file())


def _env_file() -> Path | None:
    candidate = Path.cwd() / ".env"
    return candidate if candidate.is_file() else None
