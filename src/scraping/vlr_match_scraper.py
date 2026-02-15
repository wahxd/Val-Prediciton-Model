"""VLR.gg match page parser for extracting player stats, agents, and metadata.

This module provides the PARSING layer for VLR.gg match pages. It extracts rich
metadata that Valoscribe's scraper does NOT extract:
- Player stats (ACS, K/D/A, KAST%, ADR, HS%, FK/FD) per map
- Player VLR.gg profile IDs
- Match scores and dates

Designed to work with already-fetched HTML (no HTTP requests in this class).
HTTP fetching is handled by VLREventScraper.
"""

import re
from typing import Optional

import structlog
from bs4 import BeautifulSoup

from src.scraping.team_normalizer import TeamNormalizer

log = structlog.get_logger(__name__)


class VLRMatchScraper:
    """Parser for VLR.gg match page HTML.

    Extracts player stats, agent compositions, player VLR IDs, scores, and dates
    from already-fetched VLR.gg match pages (game=all view).

    Example:
        scraper = VLRMatchScraper(team_normalizer)
        match_data = scraper.parse_match(html_string, match_url)
        # Returns dict with teams, maps, player_stats, agent_compositions, etc.
    """

    def __init__(self, team_normalizer: TeamNormalizer):
        """Initialize match scraper.

        Args:
            team_normalizer: TeamNormalizer instance for team name normalization
        """
        self.team_normalizer = team_normalizer

    def parse_match(self, html: str, match_url: str) -> dict:
        """Parse VLR.gg match page HTML to extract rich metadata.

        Args:
            html: HTML content of VLR.gg match page (game=all view)
            match_url: Match URL (for reference in returned data)

        Returns:
            Dictionary with structure:
            {
                "match_url": str,
                "teams": [str, str],  # normalized team names
                "match_score": str,   # "2-1" format
                "date": str,          # ISO YYYY-MM-DD or empty string
                "maps": [
                    {
                        "map_number": int,
                        "map_name": str,
                        "map_score": str,   # "13-9" format
                        "vod_url": str | None,
                        "starting_sides": {"team1": "attack"|"defense", "team2": ...},
                        "agent_compositions": [{"name": str, "team": str, "agent": str}, ...],
                        "player_stats": {
                            "player_name": {
                                "acs": float,
                                "kills": int,
                                "deaths": int,
                                "assists": int,
                                "kast_pct": float | None,
                                "adr": float,
                                "hs_pct": float,
                                "fk": int,
                                "fd": int,
                            }
                        },
                        "player_vlr_ids": {"player_name": int},
                    }
                ]
            }
        """
        soup = BeautifulSoup(html, 'lxml')

        # Extract teams and normalize
        teams_raw = self._extract_team_names(soup)
        teams = [self.team_normalizer.normalize(team) for team in teams_raw]

        # Extract match-level metadata
        match_score = self._extract_match_score(soup)
        date = self._extract_date(soup)

        # Extract map data
        map_data_nav = self._extract_map_navigation(soup)
        vod_urls = self._extract_vod_urls(soup)

        maps = []
        for i, (game_id, map_name) in enumerate(map_data_nav):
            map_number = i + 1
            vod_url = vod_urls[i] if i < len(vod_urls) else None

            map_result = self._extract_map_data(
                soup=soup,
                map_number=map_number,
                map_name=map_name,
                vod_url=vod_url,
                teams=teams,
                container_index=i,
            )

            if map_result:
                maps.append(map_result)

        return {
            "match_url": match_url,
            "teams": teams,
            "match_score": match_score,
            "date": date,
            "maps": maps,
        }

    def _extract_team_names(self, soup: BeautifulSoup) -> list[str]:
        """Extract team names from match header.

        Returns:
            List of 2 team names (raw from VLR, not yet normalized)
        """
        teams = []

        # Look in match header for team names
        header = soup.find('div', class_='match-header')
        if header:
            team_links = header.find_all('a', class_='match-header-link')
            for link in team_links[:2]:
                team_name_div = link.find('div', class_='wf-title-med')
                if team_name_div:
                    teams.append(team_name_div.get_text(strip=True))

        # Fallback: try game header
        if len(teams) < 2:
            game_header = soup.find('div', class_='vm-stats-game-header')
            if game_header:
                team_divs = game_header.find_all('div', class_='team-name')
                teams = [team.get_text(strip=True) for team in team_divs[:2]]

        # Final fallback
        if len(teams) != 2:
            log.warning(f"Expected 2 teams, found {len(teams)}, using placeholders")
            teams = ["Team1", "Team2"]

        return teams

    def _extract_match_score(self, soup: BeautifulSoup) -> str:
        """Extract overall match score (e.g., "2-1").

        Returns:
            Match score string or empty string if not found
        """
        # Look for match header score elements
        header = soup.find('div', class_='match-header')
        if header:
            # Score is in js-spoiler elements or match-header-vs-score divs
            score_divs = header.find_all('div', class_='js-spoiler')
            if len(score_divs) >= 2:
                score1 = score_divs[0].get_text(strip=True)
                score2 = score_divs[1].get_text(strip=True)
                return f"{score1}-{score2}"

        return ""

    def _extract_date(self, soup: BeautifulSoup) -> str:
        """Extract match date and convert to ISO YYYY-MM-DD format.

        Returns:
            ISO date string or empty string if not found
        """
        # Look for moment-tz-convert elements (VLR uses moment.js for dates)
        moment_elem = soup.find('div', class_='moment-tz-convert')
        if moment_elem and moment_elem.get('data-utc-ts'):
            # VLR stores Unix timestamp in data-utc-ts attribute
            try:
                from datetime import datetime, timezone
                timestamp = int(moment_elem['data-utc-ts'])
                dt = datetime.fromtimestamp(timestamp, timezone.utc)
                return dt.strftime('%Y-%m-%d')
            except (ValueError, KeyError):
                pass

        # Fallback: look for date text in match header
        header = soup.find('div', class_='match-header')
        if header:
            # Date might be in a div with specific classes
            date_div = header.find('div', class_='moment-tz-convert')
            if date_div:
                date_text = date_div.get_text(strip=True)
                # Try to parse common formats
                # This is best-effort; may need refinement based on actual VLR pages
                if date_text:
                    return date_text  # Return as-is for now

        return ""

    def _extract_vod_urls(self, soup: BeautifulSoup) -> list[str]:
        """Extract individual map VOD URLs (YouTube links).

        Returns:
            List of YouTube URLs for each map
        """
        vod_urls = []

        # Find the match streams/VODs section
        streams_section = soup.find('div', class_='match-streams-bets-container')
        if streams_section:
            # Get all YouTube links
            links = streams_section.find_all('a', href=True)

            for link in links:
                href = link['href']
                link_text = link.get_text(strip=True).lower()

                # Look for "Map 1", "Map 2", etc.
                if 'map ' in link_text and link_text != 'map':
                    if 'youtube.com' in href or 'youtu.be' in href:
                        vod_urls.append(href)

        return vod_urls

    def _extract_map_navigation(self, soup: BeautifulSoup) -> list[tuple[str, str]]:
        """Extract map game IDs and names from navigation section.

        Returns:
            List of (game_id, map_name) tuples
        """
        map_data = []

        # Find the map navigation
        nav = soup.find('div', class_='vm-stats-gamesnav')
        if nav:
            # Find all map selector items
            map_items = nav.find_all('div', class_='vm-stats-gamesnav-item')

            for item in map_items:
                game_id = item.get('data-game-id')

                # Skip "All Maps" item
                if game_id == 'all':
                    continue

                # Extract map name from text content
                map_text = item.get_text(strip=True)

                # Map text is like "1Ascent" or "2Lotus" - extract just the map name
                # Remove leading digits
                map_name = ''.join([c for c in map_text if not c.isdigit()]).strip()

                if game_id and map_name:
                    map_data.append((game_id, map_name))

        return map_data

    def _extract_map_data(
        self,
        soup: BeautifulSoup,
        map_number: int,
        map_name: str,
        vod_url: Optional[str],
        teams: list[str],
        container_index: int,
    ) -> Optional[dict]:
        """Extract data for a single map.

        Args:
            soup: BeautifulSoup object
            map_number: Map number (1-based)
            map_name: Map name
            vod_url: VOD URL (may be None)
            teams: List of team names
            container_index: Index of vlr-rounds container (0-based)

        Returns:
            Map data dict or None if extraction failed
        """
        try:
            # Extract player stats and VLR IDs
            player_stats, player_vlr_ids, agent_compositions = self._extract_player_stats(
                soup, teams, container_index
            )

            # Extract map score
            map_score = self._extract_map_score(soup, container_index)

            # Extract starting sides
            starting_sides = self._extract_starting_sides(soup, container_index)

            return {
                "map_number": map_number,
                "map_name": map_name,
                "map_score": map_score,
                "vod_url": vod_url,
                "starting_sides": starting_sides,
                "agent_compositions": agent_compositions,
                "player_stats": player_stats,
                "player_vlr_ids": player_vlr_ids,
            }

        except Exception as e:
            log.error(f"Failed to extract map {map_number} data: {e}")
            return None

    def _extract_player_stats(
        self,
        soup: BeautifulSoup,
        teams: list[str],
        container_index: int
    ) -> tuple[dict, dict, list[dict]]:
        """Extract player stats, VLR IDs, and agent compositions from stat tables.

        VLR.gg stat tables use <table class="wf-table-inset mod-overview"> for each team.
        Columns: Player, Agents, R, ACS, K, D, A, +/-, KAST%, ADR, HS%, FK, FD

        Args:
            soup: BeautifulSoup object
            teams: List of team names
            container_index: Map index (0-based)

        Returns:
            Tuple of (player_stats, player_vlr_ids, agent_compositions)
            - player_stats: {player_name: {acs, kills, deaths, ...}}
            - player_vlr_ids: {player_name: vlr_id}
            - agent_compositions: [{name, team, agent}, ...]
        """
        player_stats = {}
        player_vlr_ids = {}
        agent_compositions = []

        # Find all stat tables
        tables = soup.find_all('table', class_='wf-table-inset')

        # First 2 tables are "All Maps" aggregate stats
        # Map 0 uses tables 2-3, Map 1 uses tables 4-5, etc.
        table_start_idx = (container_index + 1) * 2
        table_end_idx = table_start_idx + 2
        map_tables = tables[table_start_idx:table_end_idx]

        if len(map_tables) < 2:
            log.warning(f"Expected 2 stat tables for map {container_index}, found {len(map_tables)}")

        # Process each team's table
        for team_idx, table in enumerate(map_tables):
            team_name = teams[team_idx] if team_idx < len(teams) else f"Team{team_idx + 1}"

            # Find all player rows
            rows = table.find_all('tr')

            for row in rows:
                # Skip header rows
                if row.find('th'):
                    continue

                cells = row.find_all('td')
                if len(cells) < 2:
                    continue

                # Extract player name and VLR ID from first cell
                player_cell = cells[0]
                player_link = player_cell.find('a')

                if player_link:
                    # Player name is in div with font-weight: 700
                    name_div = player_link.find('div', style=lambda s: s and 'font-weight: 700' in s)
                    if name_div:
                        player_name = name_div.get_text(strip=True)
                    else:
                        # Fallback: get first div text
                        first_div = player_link.find('div')
                        player_name = first_div.get_text(strip=True) if first_div else "Unknown"

                    # Extract VLR ID from href
                    href = player_link.get('href', '')
                    vlr_id = self.team_normalizer.extract_player_vlr_id(href)
                    if vlr_id:
                        player_vlr_ids[player_name] = vlr_id
                else:
                    player_name = player_cell.get_text(strip=True)

                # Extract agent from second cell
                agent_cell = cells[1]
                agent_img = agent_cell.find('img')
                agent_name = None
                if agent_img and agent_img.get('title'):
                    agent_name = agent_img['title'].lower()
                    agent_compositions.append({
                        "name": player_name,
                        "team": team_name,
                        "agent": agent_name,
                    })

                # Extract stats from remaining cells
                # Columns: Player, Agents, R, ACS, K, D, A, +/-, KAST%, ADR, HS%, FK, FD
                # Indices:  0       1       2   3    4  5  6   7     8       9     10    11  12
                if len(cells) >= 13:
                    try:
                        player_stats[player_name] = {
                            "acs": self._parse_float(cells[3]),
                            "kills": self._parse_int(cells[4]),
                            "deaths": self._parse_int(cells[5]),
                            "assists": self._parse_int(cells[6]),
                            "kast_pct": self._parse_float(cells[8]),  # May be None
                            "adr": self._parse_float(cells[9]),
                            "hs_pct": self._parse_float(cells[10]),
                            "fk": self._parse_int(cells[11]),
                            "fd": self._parse_int(cells[12]),
                        }
                    except (ValueError, IndexError) as e:
                        log.warning(f"Failed to parse stats for {player_name}: {e}")
                        continue

        return player_stats, player_vlr_ids, agent_compositions

    def _extract_map_score(self, soup: BeautifulSoup, container_index: int) -> str:
        """Extract per-map score (e.g., "13-9").

        Args:
            soup: BeautifulSoup object
            container_index: Map index (0-based)

        Returns:
            Map score string or empty string if not found
        """
        # Look for game headers
        game_headers = soup.find_all('div', class_='vm-stats-game-header')

        if container_index < len(game_headers):
            header = game_headers[container_index]
            # Score is in team-score divs
            score_divs = header.find_all('div', class_='score')
            if len(score_divs) >= 2:
                score1 = score_divs[0].get_text(strip=True)
                score2 = score_divs[1].get_text(strip=True)
                return f"{score1}-{score2}"

        return ""

    def _extract_starting_sides(
        self,
        soup: BeautifulSoup,
        container_index: int
    ) -> dict:
        """Extract starting sides from round timeline.

        Args:
            soup: BeautifulSoup object
            container_index: Map index (0-based)

        Returns:
            Dictionary: {"team1": "attack"|"defense", "team2": "attack"|"defense"}
        """
        # Find all round timeline containers
        all_rounds_containers = soup.find_all('div', class_='vlr-rounds')

        if not all_rounds_containers or container_index >= len(all_rounds_containers):
            log.warning("Could not find vlr-rounds container, using default starting sides")
            return {"team1": "attack", "team2": "defense"}

        # Select the correct container for this map
        rounds_container = all_rounds_containers[container_index]

        # Get the direct child vlr-rounds-row
        rounds_rows = rounds_container.find_all('div', class_='vlr-rounds-row', recursive=False)
        if not rounds_rows:
            return {"team1": "attack", "team2": "defense"}

        first_row = rounds_rows[0]
        children = first_row.find_all(recursive=False)
        if len(children) == 0:
            return {"team1": "attack", "team2": "defense"}

        # Find first round with title attribute
        first_round = None
        for child in children[1:]:  # Skip first child (team names)
            title = child.get('title')
            if title and ('Round 1' in title or title.startswith('Round 1')):
                first_round = child
                break

        if not first_round:
            return {"team1": "attack", "team2": "defense"}

        # Find the rnd-sq with mod-win to determine winner and side
        rnd_sqs = first_round.find_all('div', class_='rnd-sq')
        if len(rnd_sqs) < 2:
            return {"team1": "attack", "team2": "defense"}

        # Determine which team won and on which side
        winning_team_position = None  # 0 = top (team1), 1 = bottom (team2)
        winning_side = None

        for i, rnd_sq in enumerate(rnd_sqs[:2]):
            classes = rnd_sq.get('class', [])
            if 'mod-win' in classes:
                winning_team_position = i
                if 'mod-ct' in classes:
                    winning_side = "defense"
                elif 'mod-t' in classes:
                    winning_side = "attack"
                break

        if winning_team_position is None or winning_side is None:
            return {"team1": "attack", "team2": "defense"}

        # Assign sides (top team = team1, bottom team = team2)
        losing_side = "defense" if winning_side == "attack" else "attack"

        if winning_team_position == 0:  # team1 won
            return {"team1": winning_side, "team2": losing_side}
        else:  # team2 won
            return {"team1": losing_side, "team2": winning_side}

    def _parse_float(self, cell) -> Optional[float]:
        """Parse float from table cell, handling percentages and missing values.

        Args:
            cell: BeautifulSoup table cell

        Returns:
            Float value or None if cell is empty/invalid
        """
        text = cell.get_text(strip=True)
        if not text or text == '-' or text == '':
            return None

        # Remove % sign if present
        text = text.replace('%', '')

        try:
            return float(text)
        except ValueError:
            return None

    def _parse_int(self, cell) -> int:
        """Parse int from table cell.

        Args:
            cell: BeautifulSoup table cell

        Returns:
            Int value or 0 if cell is empty/invalid
        """
        text = cell.get_text(strip=True)
        if not text or text == '-':
            return 0

        try:
            return int(text)
        except ValueError:
            return 0
