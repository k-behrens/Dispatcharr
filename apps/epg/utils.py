import requests
from datetime import datetime
from django.core.cache import cache

def fetch_mlb_standings(season="2025"):
    """Fetch MLB team records and standings."""
    cache_key = f"mlb_standings_{season}_{datetime.now().strftime('%Y%m%d')}"
    standings = cache.get(cache_key)
    
    if standings is None:
        url = f"https://statsapi.mlb.com/api/v1/standings?leagueId=103,104&season={season}"
        try:
            response = requests.get(url, timeout=5)
            response.raise_for_status()
            data = response.json()
            standings = {}
            division_map = {
                "American League East": "AL East",
                "American League Central": "AL Central",
                "American League West": "AL West",
                "National League East": "NL East",
                "National League Central": "NL Central",
                "National League West": "NL West"
            }
            for record in data.get("records", []):
                division = division_map.get(record["division"]["name"], record["division"]["name"])
                for team_record in record.get("teamRecords", []):
                    team_name = team_record["team"]["name"].lower()
                    # Use short name (e.g., "Yankees" from "New York Yankees")
                    short_name = team_record["team"]["name"].split()[-1]
                    standings[team_name] = {
                        "short_name": short_name,
                        "wins": team_record["wins"],
                        "losses": team_record["losses"],
                        "division_rank": team_record["divisionRank"],
                        "division": division
                    }
            cache.set(cache_key, standings, timeout=86400)  # Cache for 24 hours
        except requests.RequestException as e:
            print(f"Error fetching standings: {e}")
            return {}
    
    return standings

def fetch_mlb_schedule(date_str, season="2025"):
    """Fetch MLB games for a date (YYYY-MM-DD)."""
    cache_key = f"mlb_schedule_{season}_{date_str}"
    games = cache.get(cache_key)
    
    if games is None:
        url = f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={date_str}&season={season}"
        try:
            response = requests.get(url, timeout=5)
            response.raise_for_status()
            data = response.json()
            games = data.get("dates", [{}])[0].get("games", [])
            cache.set(cache_key, games, timeout=86400)  # Cache for 24 hours
        except requests.RequestException as e:
            print(f"Error fetching schedule: {e}")
            return []
    
    return games

def enhance_mlb_description(program, season="2025"):
    """Enhance MLB program with concise records, standings, and venue."""
    category = program.get("category", "").lower()
    if "mlb" not in category:
        return program

    title = program.get("title", "").lower()
    description = program.get("desc", "")
    start_time = program.get("start", "")

    # Parse date from start time (YYYYMMDDHHMMSS)
    try:
        date_str = datetime.strptime(start_time[:8], "%Y%m%d").strftime("%Y-%m-%d")
    except ValueError:
        print(f"Invalid date for: {title}")
        return program

    # Team aliases for matching
    team_aliases = {
        "ny yankees": "new york yankees",
        "d-backs": "arizona diamondbacks",
        "sox": "red sox",
        "white sox": "chicago white sox",
        "blue jays": "toronto blue jays",
        "rays": "tampa bay rays",
        "phillies": "philadelphia phillies",
        "nats": "washington nationals"
    }
    def normalize_team_name(name):
        return team_aliases.get(name, name)

    # Fetch standings and schedule
    standings = fetch_mlb_standings(season)
    games = fetch_mlb_schedule(date_str, season)
    if not standings or not games:
        return program

    # Match teams
    teams_found = []
    title_normalized = normalize_team_name(title)
    for team_name, data in standings.items():
        if team_name in title_normalized:
            teams_found.append((team_name, data))
            if len(teams_found) == 2:
                break

    # Find venue
    venue = None
    for game in games:
        away_team = game["teams"]["away"]["team"]["name"].lower()
        home_team = game["teams"]["home"]["team"]["name"].lower()
        if all(t[0] in (away_team, home_team) for t in teams_found):
            venue = game["venue"]["name"]
            break

    # Build concise description
    if len(teams_found) == 2 and venue:
        team1_name, team1_data = teams_found[0]
        team2_name, team2_data = teams_found[1]
        # Format rank (1st, 2nd, 3rd, etc.)
        rank1 = f"{team1_data['division_rank']}{'st' if team1_data['division_rank'] == '1' else 'nd' if team1_data['division_rank'] == '2' else 'rd' if team1_data['division_rank'] == '3' else 'th'}"
        rank2 = f"{team2_data['division_rank']}{'st' if team2_data['division_rank'] == '1' else 'nd' if team2_data['division_rank'] == '2' else 'rd' if team2_data['division_rank'] == '3' else 'th'}"
        team1_display = f"{team1_data['short_name']} ({team1_data['wins']}-{team1_data['losses']}, {rank1} {team1_data['division']})"
        team2_display = f"{team2_data['short_name']} ({team2_data['wins']}-{team2_data['losses']}, {rank2} {team2_data['division']})"
        extra_info = f"{team1_display} vs. {team2_display} at {venue}."
        program["desc"] = f"{description} {extra_info}".strip()
    else:
        print(f"No match for: {title}")

    return program
