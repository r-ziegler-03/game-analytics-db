import random
from datetime import datetime, timedelta, timezone

import psycopg2
from faker import Faker

from collections import Counter

fake = Faker()

DB_NAME = "game_analytics"

NUM_PLAYERS = 3000
REGIONS = ["NA", "EU", "APAC"]
PLATFORMS = ["PC", "PlayStation", "Xbox"]

# Engagement tiers: (tier_name, weight, match_count_range)
ENGAGEMENT_TIERS = [
    ("one_and_done", 0.40, (1, 1)),
    ("moderate", 0.40, (10, 50)),
    ("heavy", 0.20, (50, 250)),
]

WINDOW_END = datetime.now(timezone.utc)
WINDOW_START = WINDOW_END - timedelta(days=365)

TIER_FIRST_SEEN_END = {
    "heavy" : WINDOW_START + timedelta(days=120),  # months 1-4
    "moderate" : WINDOW_START + timedelta(days=270),  # months 1-9
    "one_and_done" : WINDOW_END,  # anywhere in the full window
}

SITTING_SIZES = [1, 2, 3, 4, 5]  # Possible sitting sizes for matches
SITTING_SIZE_WEIGHTS = [15, 30, 30, 15, 10]  # Corresponding weights for sitting sizes

TIER_GAP_PARAMS = {
    "heavy": {"base_gap_days": 2, "growth_rate": 1.05},
    "moderate": {"base_gap_days": 5, "growth_rate": 1.15},
}

MATCH_GROUP_SIZE = 10

MODE_PARAMS = {
    "Escort": {
        "maps": ["Route 66", "Dorado", "Watchpoint: Gibraltar", "Junkertown", "Rialto", "Shambali Monastery"],
        "length_range": (480,900), # 8 to 15 minutes
    },
    "Control": {
        "maps": ["Ilios", "Lijiang Tower", "Nepal", "Oasis", "Antarctic Peninsula", "Samoa"],
        "length_range": (360, 750), # 6 to 12.5 minutes
    },
    "Hybrid": {
        "maps": ["King's Row", "Numbani", "Eichenwalde", "Hollywood", "Blizzard World", "Midtown", "Paraiso"],
        "length_range": (480, 900), # 8 to 15 minutes
    },
    "Push": {
        "maps": ["New Queen Street", "Esperança", "Colosseo", "Runasapi"],
        "length_range": (420, 900), # 7 to 15 minutes
    },
}
MODES = list(MODE_PARAMS.keys())

def get_connection():
    return psycopg2.connect(dbname=DB_NAME)

def load_heroes_by_role(conn):
    cur = conn.cursor()
    cur.execute("SELECT hero_id, hero_role FROM heroes")
    heroes_by_role = {"Tank": [], "Damage": [], "Support": []}
    for hero_id, hero_role in cur.fetchall():
        heroes_by_role[hero_role].append(hero_id)
    return heroes_by_role

def pick_team_composition(heroes_by_role):
    tank = random.sample(heroes_by_role["Tank"], 1)
    damage = random.sample(heroes_by_role["Damage"], 2)
    support = random.sample(heroes_by_role["Support"], 2)
    return tank + damage + support

def load_abilities_by_hero(conn):
    cur = conn.cursor()
    cur.execute("SELECT hero_id, ability_id, ability_type, cooldown_seconds FROM abilities")
    abilities_by_hero = {}
    for hero_id, ability_id, ability_type, cooldown_seconds in cur.fetchall():
        if ability_type == "Ultimate":
            weight = 0.025  # flat: rare but disproportionately likely to secure a kill when used
        else:
            weight = 1 / (cooldown_seconds + 5)
        abilities_by_hero.setdefault(hero_id, []).append((ability_id, weight))
    return abilities_by_hero

def pick_killing_ability(opposing_team_heroes, abilities_by_hero):
    candidates = []
    weights = []
    for hero_id in opposing_team_heroes:
        for ability_id, weight in abilities_by_hero[hero_id]:
            candidates.append((hero_id, ability_id))
            weights.append(weight)
    return random.choices(candidates, weights=weights, k=1)[0]

def simulate_participant_life(starting_hero_id, match_start, match_length_seconds, opposing_team_heroes, abilities_by_hero, all_hero_ids):
    match_end = match_start + timedelta(seconds=match_length_seconds)
    sessions = []
    death_events = []
    current_hero = starting_hero_id
    session_start = match_start
    session_count = 1
    ability_death_counts = {}
    current_time = match_start

    while True:
        gap_seconds = random.expovariate(1 / 90)  # average 90s between deaths
        next_death_time = current_time + timedelta(seconds=gap_seconds)
        if next_death_time >= match_end:
            break  # match ends before this participant dies again

        current_time = next_death_time
        killer_hero_id, ability_id = pick_killing_ability(opposing_team_heroes, abilities_by_hero)

        prior_deaths_to_ability = ability_death_counts.get(ability_id, 0)
        ragequit_prob = min(0.9, 0.011 + 0.025 * prior_deaths_to_ability)
        ability_death_counts[ability_id] = prior_deaths_to_ability + 1

        death_events.append({
            "timestamp": current_time,
            "ability_id": ability_id,
            "killer_hero_id": killer_hero_id,
        })

        if random.random() < ragequit_prob:
            sessions.append({"hero_id": current_hero, "started_at": session_start, "ended_at": current_time})
            return {"sessions": sessions, "death_events": death_events, "left_early": True}

        if session_count < 4 and random.random() < 0.08:
            sessions.append({"hero_id": current_hero, "started_at": session_start, "ended_at": current_time})
            current_hero = random.choice([h for h in all_hero_ids if h != current_hero])
            session_start = current_time
            session_count += 1

    sessions.append({"hero_id": current_hero, "started_at": session_start, "ended_at": match_end})
    return {"sessions": sessions, "death_events": death_events, "left_early": False}

def simulate_match_participants(group, heroes_by_role, abilities_by_hero, all_hero_ids, match_length_seconds):
    shuffled = group[:]
    random.shuffle(shuffled)
    team_a, team_b = shuffled[:5], shuffled[5:]

    team_a_heroes = pick_team_composition(heroes_by_role)
    team_b_heroes = pick_team_composition(heroes_by_role)

    match_start = min(timestamp for timestamp, player_id in group)

    participants = []
    for (timestamp, player_id), hero_id in zip(team_a, team_a_heroes):
        result = simulate_participant_life(hero_id, match_start, match_length_seconds, team_b_heroes, abilities_by_hero, all_hero_ids)
        participants.append({"player_id": player_id, "did_win": True, **result})
    for (timestamp, player_id), hero_id in zip(team_b, team_b_heroes):
        result = simulate_participant_life(hero_id, match_start, match_length_seconds, team_a_heroes, abilities_by_hero, all_hero_ids)
        participants.append({"player_id": player_id, "did_win": False, **result})

    return participants

def get_current_hero(participant, timestamp):
    if participant["sessions"][-1]["ended_at"] < timestamp:
        return None  # already left the match by this time
    for session in participant["sessions"]:
        if session["started_at"] <= timestamp <= session["ended_at"]:
            return session["hero_id"]
    return None

def resolve_kill_events(participants, abilities_by_hero):
    resolved = []
    for victim in participants:
        opposing = [p for p in participants if p["did_win"] != victim["did_win"]]
        for death in victim["death_events"]:
            timestamp = death["timestamp"]
            killer_hero_id = death["killer_hero_id"]

            exact_matches = [p for p in opposing if get_current_hero(p, timestamp) == killer_hero_id]
            if exact_matches:
                actor = random.choice(exact_matches)
                actor_ability_id = death["ability_id"]
            else:
                active = [p for p in opposing if get_current_hero(p, timestamp) is not None]
                if not active:
                    resolved.append({
                        "timestamp": timestamp,
                        "victim_player_id": victim["player_id"],
                        "actor_player_id": None,
                        "ability_id": death["ability_id"],
                    })
                    continue
                actor = random.choice(active)
                actor_hero_id = get_current_hero(actor, timestamp)
                candidates = abilities_by_hero[actor_hero_id]
                ability_ids = [a[0] for a in candidates]
                weights = [a[1] for a in candidates]
                actor_ability_id = random.choices(ability_ids, weights=weights, k=1)[0]

            resolved.append({
                "timestamp": timestamp,
                "victim_player_id": victim["player_id"],
                "actor_player_id": actor["player_id"],
                "ability_id": actor_ability_id,
            })
    return resolved

def random_datetime_between(start, end):
    delta_seconds = (end - start).total_seconds()
    offset = random.uniform(0, delta_seconds)
    return start + timedelta(seconds=offset)

def generate_unique_gamertag(used_gamertags):
    while True:
        candidate = fake.user_name()
        if candidate not in used_gamertags:
            used_gamertags.add(candidate)
            return candidate

def generate_players(conn, num_players):
    cur = conn.cursor()
    players_data = []
    tier_counts = Counter()
    tier_first_seen_range = {tier: [None, None] for tier in TIER_FIRST_SEEN_END}
    used_gamertags = set()
    for i in range(num_players):
        gamertag = generate_unique_gamertag(used_gamertags)
        tier_name, weight, match_range = random.choices( ENGAGEMENT_TIERS, weights=[tier[1] for tier in ENGAGEMENT_TIERS], k=1,)[0]
        region = random.choice(REGIONS)
        platform = random.choice(PLATFORMS)
        first_seen = random_datetime_between(WINDOW_START, TIER_FIRST_SEEN_END[tier_name])
        cur.execute(
            """
            INSERT INTO players (gamertag, region, platform, first_seen, last_played)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING player_id
            """,
            (gamertag, region, platform, first_seen, first_seen), 
        )
        player_id = cur.fetchone()[0]
        players_data.append({
            "player_id": player_id,
            "tier": tier_name,
            "match_range": match_range,
            "first_seen": first_seen,
        })
        tier_counts[tier_name] += 1
        lo, hi = tier_first_seen_range[tier_name]
        if lo is None or first_seen < lo:
            lo = first_seen
        if hi is None or first_seen > hi:
            hi = first_seen
        tier_first_seen_range[tier_name] = [lo, hi]
    print(tier_counts)
    print(tier_first_seen_range)
    print(len(used_gamertags))
    return players_data
    
def generate_match_timestamps(player_id, tier, first_seen, match_range):
    num_matches = random.randint(*match_range)

    if tier == "one_and_done":
        return [(first_seen, player_id)]
    
    gap_params = TIER_GAP_PARAMS[tier]
    timestamps = []
    current_time = first_seen
    sitting_index = 0
    matches_remaining = num_matches

    while matches_remaining > 0 and current_time < WINDOW_END:
        sitting_size = min(
            random.choices(SITTING_SIZES, weights=SITTING_SIZE_WEIGHTS, k=1)[0],
            matches_remaining,
        )
        for m in range(sitting_size):
            timestamps.append((current_time, player_id))
            current_time += timedelta(minutes=12)  # 10 minutes for match + 2 minutes for break
        matches_remaining -= sitting_size

        gap_days = gap_params["base_gap_days"] * (gap_params["growth_rate"] ** sitting_index)
        current_time += timedelta(days=gap_days)
        sitting_index += 1

    return timestamps

def generate_matches(conn, players_data, heroes_by_role, abilities_by_hero, all_hero_ids):
    all_timestamps = []
    for player in players_data:
        all_timestamps.extend(
            generate_match_timestamps(
                player["player_id"], player["tier"], player["first_seen"], player["match_range"]
            )
        )
    all_timestamps.sort(key=lambda pair: pair[0])

    match_groups = []
    remaining = all_timestamps

    while True:
        current_group = []
        current_group_players = set()
        leftover = []

        for pair in remaining:
            timestamp, player_id = pair
            if player_id in current_group_players:
                leftover.append(pair)
                continue
            current_group.append(pair)
            current_group_players.add(player_id)
            if len(current_group) == MATCH_GROUP_SIZE:
                match_groups.append(current_group)
                current_group = []
                current_group_players = set()

        groups_made_this_pass = (len(remaining) - len(leftover)) // MATCH_GROUP_SIZE
        if groups_made_this_pass == 0:
            break
        remaining = leftover

    print(f"total timestamps: {len(all_timestamps)}, full match groups: {len(match_groups)}, unused leftover: {len(remaining)}")
    match_ids = []
    for group in match_groups:
        match_id = insert_full_match(conn, group, heroes_by_role, abilities_by_hero, all_hero_ids)
        match_ids.append(match_id)
    print(f"Inserted {len(match_ids)} matches into the database.")
    return match_ids

def insert_full_match(conn, group, heroes_by_role, abilities_by_hero, all_hero_ids):
    cur = conn.cursor()

    mode = random.choice(MODES)
    map_name = random.choice(MODE_PARAMS[mode]["maps"])
    length_lo, length_hi = MODE_PARAMS[mode]["length_range"]
    match_length_seconds = random.randint(length_lo, length_hi)
    is_competitive = random.random() < 0.4
    match_date = min(timestamp for timestamp, player_id in group)

    cur.execute(
        """
        INSERT INTO matches (mode, is_competitive, match_length_seconds, match_date, map_name)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING match_id
        """,
        (mode, is_competitive, match_length_seconds, match_date, map_name),
    )
    match_id = cur.fetchone()[0]

    participants = simulate_match_participants(group, heroes_by_role, abilities_by_hero, all_hero_ids, match_length_seconds)

    for participant in participants:
        cur.execute(
            """
            INSERT INTO match_participants (match_id, player_id, did_win, left_early, rank_before_match, rank_after_match)
            VALUES (%s, %s, %s, %s, NULL, NULL)
            RETURNING participant_id
            """,
            (match_id, participant["player_id"], participant["did_win"], participant["left_early"]),
        )
        participant["participant_id"] = cur.fetchone()[0]

        for session in participant["sessions"]:
            cur.execute(
                """
                INSERT INTO participant_heroes (participant_id, hero_id, started_at, ended_at, damage_done, healing_done, eliminations, deaths, assists, number_of_ultimates_used)
                VALUES (%s, %s, %s, %s, 0, 0, 0, 0, 0, 0)
                RETURNING session_id
                """,
                (participant["participant_id"], session["hero_id"], session["started_at"], session["ended_at"]),
            )
            session["session_id"] = cur.fetchone()[0]

    resolved = resolve_kill_events(participants, abilities_by_hero)
    by_player = {p["player_id"]: p for p in participants}

    for kill in resolved:
        if kill["actor_player_id"] is None:
            continue  # rare edge case, no valid opposing killer -- skip for now

        victim = by_player[kill["victim_player_id"]]
        actor = by_player[kill["actor_player_id"]]
        victim_hero = get_current_hero(victim, kill["timestamp"])
        actor_hero = get_current_hero(actor, kill["timestamp"])

        victim_session_id = next(s["session_id"] for s in victim["sessions"] if s["hero_id"] == victim_hero and s["started_at"] <= kill["timestamp"] <= s["ended_at"])
        actor_session_id = next(s["session_id"] for s in actor["sessions"] if s["hero_id"] == actor_hero and s["started_at"] <= kill["timestamp"] <= s["ended_at"])

        cur.execute(
            "INSERT INTO events (actor_session_id, target_session_id, event_type, ability_id, event_timestamp) VALUES (%s, %s, 'kill', %s, %s)",
            (actor_session_id, victim_session_id, kill["ability_id"], kill["timestamp"]),
        )
        cur.execute(
            "INSERT INTO events (actor_session_id, target_session_id, event_type, ability_id, event_timestamp) VALUES (%s, %s, 'death', %s, %s)",
            (victim_session_id, actor_session_id, kill["ability_id"], kill["timestamp"]),
        )

    return match_id

def main():
    conn = get_connection()
    try:
        heroes_by_role = load_heroes_by_role(conn)
        abilities_by_hero = load_abilities_by_hero(conn)
        all_hero_ids = [h for ids in heroes_by_role.values() for h in ids]

        players_data = generate_players(conn, NUM_PLAYERS)
        match_ids = generate_matches(conn, players_data, heroes_by_role, abilities_by_hero, all_hero_ids)
        conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    conn = get_connection()
    try:
        heroes_by_role = load_heroes_by_role(conn)
        abilities_by_hero = load_abilities_by_hero(conn)
        all_hero_ids = [h for ids in heroes_by_role.values() for h in ids]

        players_data = generate_players(conn, NUM_PLAYERS)
        match_ids = generate_matches(conn, players_data, heroes_by_role, abilities_by_hero, all_hero_ids)
        print(players_data[:5])  # Print first 5 players for verification
        conn.rollback()
    finally:
        conn.close()
    #main()
