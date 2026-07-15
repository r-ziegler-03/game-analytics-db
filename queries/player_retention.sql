WITH player_cohorts AS (
    -- each player's cohort: the month they first appeared
    SELECT
        player_id,
        DATE_TRUNC('month', first_seen) AS cohort_month
    FROM players
),

player_active_months AS (
    -- every distinct month a player had at least one real match
    SELECT DISTINCT
        mp.player_id,
        DATE_TRUNC('month', m.match_date) AS active_month
    FROM match_participants mp
    JOIN matches m ON m.match_id = mp.match_id
),

cohort_activity AS (
    -- join cohort to activity, compute how many months after their cohort start each active month is
    SELECT
        pc.cohort_month,
        pc.player_id,
        ((EXTRACT(YEAR FROM pam.active_month) - EXTRACT(YEAR FROM pc.cohort_month)) * 12
            + (EXTRACT(MONTH FROM pam.active_month) - EXTRACT(MONTH FROM pc.cohort_month)))::INT AS periods_since_start
    FROM player_cohorts pc
    JOIN player_active_months pam ON pam.player_id = pc.player_id
),

cohort_sizes AS (
    -- total players in each cohort (the retention denominator)
    SELECT cohort_month, COUNT(*) AS cohort_size
    FROM player_cohorts
    GROUP BY cohort_month
)

SELECT
    ca.cohort_month,
    ca.periods_since_start,
    COUNT(DISTINCT ca.player_id) AS retained_players,
    cs.cohort_size,
    ROUND(100.0 * COUNT(DISTINCT ca.player_id) / cs.cohort_size, 2) AS pct_retained
FROM cohort_activity ca
JOIN cohort_sizes cs ON cs.cohort_month = ca.cohort_month
-- matches.match_date is a group-level minimum timestamp across the 10 players in that
-- match, not any individual player's own timestamp, so a small number of players can show
-- an "active month" slightly before their own cohort month. Excluded here as noise (~10
-- players total across the whole dataset).
WHERE ca.periods_since_start >= 0
GROUP BY ca.cohort_month, ca.periods_since_start, cs.cohort_size
ORDER BY ca.cohort_month, ca.periods_since_start;