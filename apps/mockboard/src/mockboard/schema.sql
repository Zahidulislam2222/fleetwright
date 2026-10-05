-- Mock load board schema (its own database). Idempotent; applied at startup by the board.
CREATE TABLE IF NOT EXISTS board_accounts (
  id            serial PRIMARY KEY,
  username      text NOT NULL UNIQUE,
  email         text NOT NULL,
  password_hash text NOT NULL,
  created_at    timestamptz NOT NULL DEFAULT clock_timestamp()
);

-- Step 1 of login: password accepted, OTP emailed, waiting for the code.
CREATE TABLE IF NOT EXISTS board_login_challenges (
  token_hash  text PRIMARY KEY,
  account_id  int NOT NULL REFERENCES board_accounts(id) ON DELETE CASCADE,
  otp_hash    text NOT NULL,
  attempts    int NOT NULL DEFAULT 0,
  expires_at  timestamptz NOT NULL,
  created_at  timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE TABLE IF NOT EXISTS board_sessions (
  token_hash     text PRIMARY KEY,
  account_id     int NOT NULL REFERENCES board_accounts(id) ON DELETE CASCADE,
  csrf           text NOT NULL,
  created_at     timestamptz NOT NULL DEFAULT clock_timestamp(),
  expires_at     timestamptz NOT NULL,
  revoked        boolean NOT NULL DEFAULT false,
  window_start   timestamptz NOT NULL DEFAULT clock_timestamp(),
  window_count   int NOT NULL DEFAULT 0,
  captcha_answer text,
  minute_start   timestamptz NOT NULL DEFAULT clock_timestamp(),
  minute_count   int NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS board_sessions_account ON board_sessions (account_id) WHERE NOT revoked;

-- Loads. published_at is the ground truth the latency report starts from (database clock).
CREATE TABLE IF NOT EXISTS loads (
  id            bigserial PRIMARY KEY,
  ref           text GENERATED ALWAYS AS ('L-' || lpad(id::text, 8, '0')) STORED UNIQUE,
  origin        text NOT NULL,
  destination   text NOT NULL,
  equipment     text NOT NULL,
  weight_lb     int NOT NULL,
  miles         int NOT NULL,
  rate_usd      int NOT NULL,
  pickup_at     timestamptz NOT NULL,
  published_at  timestamptz NOT NULL DEFAULT clock_timestamp(),
  booked_by     int REFERENCES board_accounts(id),
  booked_by_competitor text,
  booked_at     timestamptz,
  CONSTRAINT one_booker CHECK (booked_by IS NULL OR booked_by_competitor IS NULL)
);
CREATE INDEX IF NOT EXISTS loads_published ON loads (published_at);
CREATE INDEX IF NOT EXISTS loads_booked_by ON loads (booked_by, booked_at) WHERE booked_by IS NOT NULL;

-- Every booking attempt, successful or not: the duplicate-action audit reads this table.
CREATE TABLE IF NOT EXISTS booking_attempts (
  id          bigserial PRIMARY KEY,
  load_id     bigint NOT NULL REFERENCES loads(id) ON DELETE CASCADE,
  account_id  int REFERENCES board_accounts(id),
  competitor  text,
  at          timestamptz NOT NULL DEFAULT clock_timestamp(),
  outcome     text NOT NULL CHECK (outcome IN ('booked', 'already_booked', 'ack_lost'))
);
CREATE INDEX IF NOT EXISTS booking_attempts_load ON booking_attempts (load_id);
CREATE INDEX IF NOT EXISTS booking_attempts_at ON booking_attempts (at);

-- One row: adversity toggles and feed rate, shared by every board instance.
CREATE TABLE IF NOT EXISTS board_settings (
  id          int PRIMARY KEY CHECK (id = 1),
  value       jsonb NOT NULL,
  updated_at  timestamptz NOT NULL DEFAULT clock_timestamp()
);

-- Admin changes (toggles, forced expiry) for the ground-truth timeline.
CREATE TABLE IF NOT EXISTS board_admin_events (
  id      bigserial PRIMARY KEY,
  at      timestamptz NOT NULL DEFAULT clock_timestamp(),
  kind    text NOT NULL,
  detail  jsonb NOT NULL
);

-- Loads joined with the booking account's username: every read goes through this view, so queries
-- stay static SQL strings.
CREATE OR REPLACE VIEW load_rows AS
  SELECT l.id, l.ref, l.origin, l.destination, l.equipment, l.weight_lb, l.miles, l.rate_usd, l.pickup_at,
         l.published_at, l.booked_at, l.booked_by, l.booked_by_competitor, ba.username AS booked_by_username
  FROM loads l LEFT JOIN board_accounts ba ON ba.id = l.booked_by;
