CREATE TABLE players (
    player_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    gamertag TEXT UNIQUE NOT NULL,
    region TEXT NOT NULL,
    platform TEXT NOT NULL,
    first_seen TIMESTAMPTZ NOT NULL,
    last_played TIMESTAMPTZ NOT NULL
);

CREATE TABLE matches (
    match_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    mode TEXT NOT NULL,
    is_competitive BOOLEAN NOT NULL,
    match_length_seconds INT NOT NULL,
    match_date TIMESTAMPTZ NOT NULL,
    map_name TEXT NOT NULL
);

CREATE TABLE heroes (
    hero_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    hero_name TEXT UNIQUE NOT NULL,
    hero_role TEXT NOT NULL CHECK (hero_role IN ('Tank', 'Damage', 'Support')),
    health INT NOT NULL,
    base_damage INT NOT NULL
);

CREATE TABLE abilities (
    ability_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    hero_id INT NOT NULL REFERENCES heroes(hero_id) ON DELETE CASCADE,
    ability_name TEXT NOT NULL,
    ability_type TEXT NOT NULL CHECK (ability_type IN ('Primary', 'Secondary', 'Ultimate')),
    cooldown_seconds INT NOT NULL
);

CREATE TABLE match_participants (
    participant_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    match_id INT NOT NULL REFERENCES matches(match_id) ON DELETE CASCADE,
    player_id INT NOT NULL REFERENCES players(player_id) ON DELETE CASCADE,
    did_win BOOLEAN NOT NULL,
    left_early BOOLEAN NOT NULL,
    rank_before_match INT,
    rank_after_match INT
);

CREATE TABLE participant_heroes (
    session_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    participant_id INT NOT NULL REFERENCES match_participants(participant_id) ON DELETE CASCADE,
    hero_id INT NOT NULL REFERENCES heroes(hero_id) ON DELETE CASCADE,
    started_at TIMESTAMPTZ NOT NULL,
    ended_at TIMESTAMPTZ NOT NULL,
    damage_done INT NOT NULL,
    healing_done INT NOT NULL,
    eliminations INT NOT NULL,
    deaths INT NOT NULL,
    assists INT NOT NULL,
    number_of_ultimates_used INT NOT NULL
);

CREATE TABLE events (
    event_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    actor_session_id INT NOT NULL REFERENCES participant_heroes(session_id) ON DELETE CASCADE,
    target_session_id INT REFERENCES participant_heroes(session_id) ON DELETE SET NULL,
    event_type TEXT NOT NULL CHECK (event_type IN ('kill', 'death', 'ability_used', 'ultimate_used', 'left_match')),
    ability_id INT REFERENCES abilities(ability_id) ON DELETE SET NULL,
    event_timestamp TIMESTAMPTZ NOT NULL
);

-- actor_session_id first: queries filter to one session's events, then narrow by event_type
CREATE INDEX idx_events_actor_type ON events (actor_session_id, event_type);

-- target_session_id first: assists lookup filters to one victim's incoming events,
-- then narrows by event_type and a timestamp range
CREATE INDEX idx_events_target_type_timestamp ON events (target_session_id, event_type, event_timestamp);