-- Pharma Commercial Analytics Engine — schema
-- 4 tables: reps (sales reps), hcps (doctors/healthcare providers),
-- calls (rep visit log), rx (monthly prescription volume)

DROP TABLE IF EXISTS calls;
DROP TABLE IF EXISTS rx;
DROP TABLE IF EXISTS hcps;
DROP TABLE IF EXISTS reps;

CREATE TABLE reps (
    rep_id           INTEGER PRIMARY KEY,
    rep_name         TEXT,
    region           TEXT,
    quarterly_quota  INTEGER   -- total TRx expected from their panel per quarter
);

CREATE TABLE hcps (
    hcp_id           INTEGER PRIMARY KEY,
    specialty        TEXT,
    region           TEXT,
    potential_score  INTEGER,  -- 1-99, synthetic "market potential" for this doctor
    assigned_rep_id  INTEGER REFERENCES reps(rep_id)  -- territory ownership
);

CREATE TABLE calls (
    call_id    INTEGER PRIMARY KEY,
    rep_id     INTEGER REFERENCES reps(rep_id),
    hcp_id     INTEGER REFERENCES hcps(hcp_id),
    call_date  TEXT,          -- ISO date
    channel    TEXT           -- 'in-person'  'virtual'  'email'
);

CREATE TABLE rx (
    rx_id    INTEGER PRIMARY KEY,
    hcp_id   INTEGER REFERENCES hcps(hcp_id),
    product  TEXT,
    month    TEXT,            -- first day of month, ISO date
    trx      INTEGER,         -- total prescriptions
    nrx      INTEGER          -- new prescriptions
);
