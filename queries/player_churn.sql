-- Churn (30+ days inactive as of the latest match in the dataset) vs. ragequit history,
-- stratified by total-match-count quartile to control for engagement level.
--
-- Finding: an earlier unstratified version of this query showed a confounded pattern
-- (low-ragequit players churning less than never/moderate-ragequit players). Once
-- stratified by quartile, that effect mostly disappears: churn is driven almost entirely
-- by overall engagement level (quartile 1 churns ~95-100% regardless of ragequit rate;
-- quartile 4 churns ~11.5% and is entirely in the "low" ragequit bucket, since heavy
-- players dilute any ragequit incidents into a small percentage of a large match history).
-- No clear independent ragequit-driven churn effect survives controlling for engagement.
-- Some quartile 2/3 cells have very small sample sizes (n=1, n=4) and shouldn't be
-- over-interpreted.

WITH reference_date AS (
    SELECT MAX(match_date) AS as_of FROM matches
),

player_match_stats AS (
    SELECT
        player_id,
        COUNT(*) AS total_matches,
        COUNT(*) FILTER (WHERE left_early) AS ragequit_matches,
        ROUND(100.0 * COUNT(*) FILTER (WHERE left_early) / COUNT(*), 2) AS ragequit_rate_pct
    FROM match_participants
    GROUP BY player_id
    HAVING COUNT(*) > 1  -- exclude one-and-done players (rate is meaningless with 1 match)
),

player_match_bands AS (
    SELECT
        *,
        NTILE(4) OVER (ORDER BY total_matches) AS match_count_quartile
    FROM player_match_stats
),

player_churn AS (
    SELECT
        p.player_id,
        (r.as_of - p.last_played) >= INTERVAL '30 days' AS is_churned
    FROM players p
    CROSS JOIN reference_date r
)

SELECT
    pmb.match_count_quartile,
    CASE
        WHEN pmb.ragequit_rate_pct = 0 THEN '1: never (0%)'
        WHEN pmb.ragequit_rate_pct <= 25 THEN '2: low (0-25%)'
        WHEN pmb.ragequit_rate_pct <= 50 THEN '3: moderate (25-50%)'
        ELSE '4: high (50%+)'
    END AS ragequit_bucket,
    COUNT(*) AS num_players,
    COUNT(*) FILTER (WHERE pc.is_churned) AS churned_players,
    ROUND(100.0 * COUNT(*) FILTER (WHERE pc.is_churned) / COUNT(*), 2) AS churn_rate_pct
FROM player_match_bands pmb
JOIN player_churn pc ON pc.player_id = pmb.player_id
GROUP BY pmb.match_count_quartile, ragequit_bucket
ORDER BY pmb.match_count_quartile, ragequit_bucket;
