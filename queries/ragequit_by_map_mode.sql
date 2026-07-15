-- Ragequit rate by mode/map. Control mode consistently shows the lowest rate (~10-11%)
-- across every one of its maps, vs. ~13.5-15% for Escort/Hybrid/Push. This tracks with
-- match length: Control has the shortest length range of any mode (6-12.5 min vs.
-- 7-15 min for the others), and since the ragequit mechanic is driven by *repeated*
-- deaths to the same ability accumulating over a match, shorter matches simply produce
-- fewer total death events and fewer chances to ever hit that repeat threshold. A real,
-- explainable emergent effect, not noise or a generation bug.

SELECT
    m.mode,
    m.map_name,
    COUNT(*) AS total_participants,
    COUNT(*) FILTER (WHERE mp.left_early) AS ragequits,
    ROUND(100.0 * COUNT(*) FILTER (WHERE mp.left_early) / COUNT(*), 2) AS ragequit_rate_pct
FROM match_participants mp
JOIN matches m ON m.match_id = mp.match_id
GROUP BY m.mode, m.map_name
ORDER BY ragequit_rate_pct DESC;
