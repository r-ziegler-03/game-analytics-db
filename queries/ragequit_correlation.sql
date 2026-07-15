WITH participant_deaths AS (
    -- every death event, scoped to participant (not session) since a participant's
    -- actor_session_id can change mid-match if they switch heroes
    SELECT
        mp.participant_id,
        mp.left_early,
        e.ability_id,
        e.event_timestamp,
        COUNT(*) OVER (
            PARTITION BY mp.participant_id, e.ability_id
            ORDER BY e.event_timestamp
        ) AS deaths_to_this_ability_so_far
    FROM events e
    JOIN participant_heroes ph ON ph.session_id = e.actor_session_id
    JOIN match_participants mp ON mp.participant_id = ph.participant_id
    WHERE e.event_type = 'death'
),

last_death_per_participant AS (
    -- just each participant's final death (the one that could've triggered a ragequit)
    SELECT DISTINCT ON (participant_id)
        participant_id,
        left_early,
        deaths_to_this_ability_so_far
    FROM participant_deaths
    ORDER BY participant_id, event_timestamp DESC
)

SELECT
    CASE WHEN deaths_to_this_ability_so_far >= 2 THEN 'repeated_ability_death' ELSE 'other_reason' END AS quit_reason,
    COUNT(*) AS num_players_left_early
FROM last_death_per_participant
WHERE left_early = true
GROUP BY quit_reason;


-- Follow-up: rather than only looking at players who already quit, compare the actual
-- quit RATE for repeated-ability deaths vs. first-time-to-that-ability deaths, across
-- every death event in the dataset (not just the ones that happened to end a match).
WITH participant_deaths AS (
    SELECT
        mp.participant_id,
        mp.left_early,
        e.ability_id,
        e.event_timestamp,
        COUNT(*) OVER (
            PARTITION BY mp.participant_id, e.ability_id
            ORDER BY e.event_timestamp
        ) AS deaths_to_this_ability_so_far,
        -- was this death the last one this participant logged in the match?
        e.event_timestamp = MAX(e.event_timestamp) OVER (PARTITION BY mp.participant_id) AS is_final_death
    FROM events e
    JOIN participant_heroes ph ON ph.session_id = e.actor_session_id
    JOIN match_participants mp ON mp.participant_id = ph.participant_id
    WHERE e.event_type = 'death'
),
classified_deaths AS (
    SELECT
        CASE WHEN deaths_to_this_ability_so_far >= 2 THEN 'repeated_ability_death' ELSE 'first_time_death' END AS death_type,
        -- a death only "triggered" a quit if it was both the participant's last death AND they left early
        (is_final_death AND left_early) AS triggered_quit
    FROM participant_deaths
)
SELECT
    death_type,
    COUNT(*) AS total_deaths,
    COUNT(*) FILTER (WHERE triggered_quit) AS quits_triggered,
    ROUND(100.0 * COUNT(*) FILTER (WHERE triggered_quit) / COUNT(*), 2) AS quit_rate_pct
FROM classified_deaths
GROUP BY death_type
ORDER BY death_type;