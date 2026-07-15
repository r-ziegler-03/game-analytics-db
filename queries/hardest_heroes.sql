-- "Hardest hero" per role: a composite of win rate and KDA, each converted to a
-- percentile rank within the hero's own role (so Tanks are only compared to other
-- Tanks, etc.) and averaged. Lower composite score = harder (worse on both dimensions
-- relative to role peers).
--
-- Caveat: win rate is essentially flat across every hero (all ~49-51%), since hero
-- choice was never modeled as influencing match outcome in the generator (did_win is
-- decided at team-assignment time, independent of hero picks). So the win-rate half of
-- the composite is mostly noise here, and the ranking is really being driven by the KDA
-- component. Kept as a genuine two-factor composite anyway, since a hero-vs-outcome
-- relationship is exactly the kind of thing this metric would need to be able to surface
-- if the underlying data modeled it.

WITH hero_session_stats AS (
    SELECT
        h.hero_id,
        h.hero_name,
        h.hero_role,
        COUNT(*) AS total_sessions,
        ROUND(100.0 * COUNT(*) FILTER (WHERE mp.did_win) / COUNT(*), 2) AS win_rate_pct,
        ROUND(AVG((ph.eliminations + ph.assists)::numeric / GREATEST(ph.deaths, 1)), 2) AS avg_kda
    FROM participant_heroes ph
    JOIN match_participants mp ON mp.participant_id = ph.participant_id
    JOIN heroes h ON h.hero_id = ph.hero_id
    GROUP BY h.hero_id, h.hero_name, h.hero_role
),

hero_percentiles AS (
    SELECT
        *,
        PERCENT_RANK() OVER (PARTITION BY hero_role ORDER BY win_rate_pct ASC) AS win_rate_percentile,
        PERCENT_RANK() OVER (PARTITION BY hero_role ORDER BY avg_kda ASC) AS kda_percentile
    FROM hero_session_stats
)

SELECT
    hero_role,
    hero_name,
    total_sessions,
    win_rate_pct,
    avg_kda,
    ROUND(((win_rate_percentile + kda_percentile) / 2)::numeric, 3) AS composite_difficulty_score
FROM hero_percentiles
ORDER BY hero_role, composite_difficulty_score ASC;
