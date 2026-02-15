"""Tests for VLRMatchScraper."""

import pytest
from src.scraping.vlr_match_scraper import VLRMatchScraper
from src.scraping.team_normalizer import TeamNormalizer


# Realistic HTML fixture representing a VLR.gg match page
# This is a minimal but realistic representation of VLR.gg's HTML structure
FIXTURE_MATCH_HTML = """
<!DOCTYPE html>
<html>
<head><title>SEN vs NRG - VLR.gg</title></head>
<body>
    <div class="match-header">
        <a class="match-header-link" href="/team/2">
            <img src="/logo/sentinels.png" />
            <div class="wf-title-med">Sentinels</div>
        </a>
        <div class="match-header-vs">
            <div class="match-header-vs-score">
                <div class="js-spoiler">2</div>
                <div class="match-header-vs-score-sep">:</div>
                <div class="js-spoiler">1</div>
            </div>
        </div>
        <a class="match-header-link" href="/team/1">
            <img src="/logo/nrg.png" />
            <div class="wf-title-med">NRG</div>
        </a>
        <div class="moment-tz-convert" data-utc-ts="1704067200">Jan 1, 2024</div>
    </div>

    <div class="vm-stats-gamesnav">
        <div class="vm-stats-gamesnav-item" data-game-id="all">All Maps</div>
        <div class="vm-stats-gamesnav-item" data-game-id="123">1Ascent</div>
        <div class="vm-stats-gamesnav-item" data-game-id="124">2Bind</div>
    </div>

    <div class="match-streams-bets-container">
        <a href="https://www.youtube.com/watch?v=MAP1_VOD">Map 1 VOD</a>
        <a href="https://www.youtube.com/watch?v=MAP2_VOD">Map 2 VOD</a>
    </div>

    <!-- All Maps aggregate stats (tables 0-1) -->
    <table class="wf-table-inset mod-overview">
        <tr><th>Player</th><th>Agent</th><th>R</th><th>ACS</th><th>K</th><th>D</th><th>A</th><th>+/-</th><th>KAST%</th><th>ADR</th><th>HS%</th><th>FK</th><th>FD</th></tr>
        <tr>
            <td><a href="/player/1001/tenz"><div style="font-weight: 700">TenZ</div></a></td>
            <td><img title="jett" /></td>
            <td>1.5</td><td>280</td><td>50</td><td>40</td><td>10</td><td>+10</td><td>75</td><td>180</td><td>25</td><td>8</td><td>2</td>
        </tr>
    </table>
    <table class="wf-table-inset mod-overview">
        <tr><th>Player</th><th>Agent</th><th>R</th><th>ACS</th><th>K</th><th>D</th><th>A</th><th>+/-</th><th>KAST%</th><th>ADR</th><th>HS%</th><th>FK</th><th>FD</th></tr>
        <tr>
            <td><a href="/player/2001/fns"><div style="font-weight: 700">FNS</div></a></td>
            <td><img title="viper" /></td>
            <td>0.8</td><td>150</td><td>30</td><td>45</td><td>20</td><td>-15</td><td>60</td><td>100</td><td>18</td><td>1</td><td>5</td>
        </tr>
    </table>

    <!-- Map 1 (Ascent) stats (tables 2-3) -->
    <div class="vm-stats-game-header">
        <div class="team-name">Sentinels</div>
        <div class="score">13</div>
        <div class="score">9</div>
        <div class="team-name">NRG</div>
    </div>
    <table class="wf-table-inset mod-overview">
        <tr><th>Player</th><th>Agent</th><th>R</th><th>ACS</th><th>K</th><th>D</th><th>A</th><th>+/-</th><th>KAST%</th><th>ADR</th><th>HS%</th><th>FK</th><th>FD</th></tr>
        <tr>
            <td><a href="/player/1001/tenz"><div style="font-weight: 700">TenZ</div></a></td>
            <td><img title="jett" /></td>
            <td>1.8</td><td>320</td><td>25</td><td>18</td><td>5</td><td>+7</td><td>80</td><td>200</td><td>28</td><td>4</td><td>1</td>
        </tr>
        <tr>
            <td><a href="/player/1002/zekken"><div style="font-weight: 700">zekken</div></a></td>
            <td><img title="raze" /></td>
            <td>1.5</td><td>280</td><td>22</td><td>19</td><td>3</td><td>+3</td><td>75</td><td>180</td><td>22</td><td>3</td><td>2</td>
        </tr>
    </table>
    <table class="wf-table-inset mod-overview">
        <tr><th>Player</th><th>Agent</th><th>R</th><th>ACS</th><th>K</th><th>D</th><th>A</th><th>+/-</th><th>KAST%</th><th>ADR</th><th>HS%</th><th>FK</th><th>FD</th></tr>
        <tr>
            <td><a href="/player/2001/fns"><div style="font-weight: 700">FNS</div></a></td>
            <td><img title="viper" /></td>
            <td>0.9</td><td>180</td><td>15</td><td>22</td><td>8</td><td>-7</td><td>65</td><td>120</td><td>20</td><td>1</td><td>3</td>
        </tr>
        <tr>
            <td><a href="/player/2002/crashies"><div style="font-weight: 700">crashies</div></a></td>
            <td><img title="sova" /></td>
            <td>1.0</td><td>200</td><td>18</td><td>20</td><td>10</td><td>-2</td><td>70</td><td>140</td><td>18</td><td>2</td><td>3</td>
        </tr>
    </table>

    <!-- Map 1 round timeline -->
    <div class="vlr-rounds">
        <div class="vlr-rounds-row">
            <div>
                <div class="team"><img src="/logo/sentinels.png" />SEN</div>
                <div class="team"><img src="/logo/nrg.png" />NRG</div>
            </div>
            <div title="Round 1: Sentinels">
                <div class="rnd-sq mod-win mod-t"></div>
                <div class="rnd-sq"></div>
            </div>
        </div>
    </div>

    <!-- Map 2 (Bind) stats (tables 4-5) -->
    <div class="vm-stats-game-header">
        <div class="team-name">Sentinels</div>
        <div class="score">11</div>
        <div class="score">13</div>
        <div class="team-name">NRG</div>
    </div>
    <table class="wf-table-inset mod-overview">
        <tr><th>Player</th><th>Agent</th><th>R</th><th>ACS</th><th>K</th><th>D</th><th>A</th><th>+/-</th><th>KAST%</th><th>ADR</th><th>HS%</th><th>FK</th><th>FD</th></tr>
        <tr>
            <td><a href="/player/1001/tenz"><div style="font-weight: 700">TenZ</div></a></td>
            <td><img title="raze" /></td>
            <td>1.2</td><td>240</td><td>20</td><td>22</td><td>5</td><td>-2</td><td>70</td><td>160</td><td>22</td><td>4</td><td>1</td>
        </tr>
        <tr>
            <td><a href="/player/1002/zekken"><div style="font-weight: 700">zekken</div></a></td>
            <td><img title="yoru" /></td>
            <td>0.9</td><td>180</td><td>16</td><td>24</td><td>4</td><td>-8</td><td>60</td><td>120</td><td>18</td><td>1</td><td>4</td>
        </tr>
    </table>
    <table class="wf-table-inset mod-overview">
        <tr><th>Player</th><th>Agent</th><th>R</th><th>ACS</th><th>K</th><th>D</th><th>A</th><th>+/-</th><th>KAST%</th><th>ADR</th><th>HS%</th><th>FK</th><th>FD</th></tr>
        <tr>
            <td><a href="/player/2001/fns"><div style="font-weight: 700">FNS</div></a></td>
            <td><img title="omen" /></td>
            <td>1.3</td><td>220</td><td>23</td><td>18</td><td>12</td><td>+5</td><td>78</td><td>150</td><td>19</td><td>3</td><td>2</td>
        </tr>
        <tr>
            <td><a href="/player/2002/crashies"><div style="font-weight: 700">crashies</div></a></td>
            <td><img title="fade" /></td>
            <td>1.1</td><td>210</td><td>21</td><td>19</td><td>9</td><td>+2</td><td>72</td><td>145</td><td>20</td><td>2</td><td>1</td>
        </tr>
    </table>

    <!-- Map 2 round timeline -->
    <div class="vlr-rounds">
        <div class="vlr-rounds-row">
            <div>
                <div class="team"><img src="/logo/sentinels.png" />SEN</div>
                <div class="team"><img src="/logo/nrg.png" />NRG</div>
            </div>
            <div title="Round 1: NRG">
                <div class="rnd-sq"></div>
                <div class="rnd-sq mod-win mod-ct"></div>
            </div>
        </div>
    </div>
</body>
</html>
"""


@pytest.fixture
def team_normalizer():
    """Create TeamNormalizer for tests."""
    return TeamNormalizer()


@pytest.fixture
def scraper(team_normalizer):
    """Create VLRMatchScraper for tests."""
    return VLRMatchScraper(team_normalizer)


def test_parse_match_extracts_teams(scraper):
    """Test that parse_match extracts correct team names."""
    result = scraper.parse_match(FIXTURE_MATCH_HTML, "https://www.vlr.gg/12345/sen-vs-nrg")

    assert result["teams"] == ["Sentinels", "NRG"]


def test_parse_match_extracts_match_score(scraper):
    """Test that parse_match extracts match score."""
    result = scraper.parse_match(FIXTURE_MATCH_HTML, "https://www.vlr.gg/12345/sen-vs-nrg")

    assert result["match_score"] == "2-1"


def test_parse_match_extracts_date(scraper):
    """Test that parse_match extracts date."""
    result = scraper.parse_match(FIXTURE_MATCH_HTML, "https://www.vlr.gg/12345/sen-vs-nrg")

    # Unix timestamp 1704067200 = 2024-01-01
    assert result["date"] == "2024-01-01"


def test_parse_match_extracts_map_data(scraper):
    """Test that parse_match extracts map metadata."""
    result = scraper.parse_match(FIXTURE_MATCH_HTML, "https://www.vlr.gg/12345/sen-vs-nrg")

    assert len(result["maps"]) == 2

    # Map 1
    map1 = result["maps"][0]
    assert map1["map_number"] == 1
    assert map1["map_name"] == "Ascent"
    assert map1["map_score"] == "13-9"
    assert map1["vod_url"] == "https://www.youtube.com/watch?v=MAP1_VOD"

    # Map 2
    map2 = result["maps"][1]
    assert map2["map_number"] == 2
    assert map2["map_name"] == "Bind"
    assert map2["map_score"] == "11-13"
    assert map2["vod_url"] == "https://www.youtube.com/watch?v=MAP2_VOD"


def test_parse_match_extracts_player_stats(scraper):
    """Test that parse_match extracts player stats with expected keys."""
    result = scraper.parse_match(FIXTURE_MATCH_HTML, "https://www.vlr.gg/12345/sen-vs-nrg")

    map1 = result["maps"][0]
    player_stats = map1["player_stats"]

    # Check TenZ's stats from Map 1
    assert "TenZ" in player_stats
    tenz_stats = player_stats["TenZ"]

    assert tenz_stats["acs"] == 320.0
    assert tenz_stats["kills"] == 25
    assert tenz_stats["deaths"] == 18
    assert tenz_stats["assists"] == 5
    assert tenz_stats["kast_pct"] == 80.0
    assert tenz_stats["adr"] == 200.0
    assert tenz_stats["hs_pct"] == 28.0
    assert tenz_stats["fk"] == 4
    assert tenz_stats["fd"] == 1

    # Check FNS's stats from Map 1
    assert "FNS" in player_stats
    fns_stats = player_stats["FNS"]

    assert fns_stats["acs"] == 180.0
    assert fns_stats["kills"] == 15
    assert fns_stats["deaths"] == 22


def test_parse_match_extracts_player_vlr_ids(scraper):
    """Test that parse_match extracts player VLR IDs from player links."""
    result = scraper.parse_match(FIXTURE_MATCH_HTML, "https://www.vlr.gg/12345/sen-vs-nrg")

    map1 = result["maps"][0]
    player_vlr_ids = map1["player_vlr_ids"]

    assert player_vlr_ids["TenZ"] == 1001
    assert player_vlr_ids["zekken"] == 1002
    assert player_vlr_ids["FNS"] == 2001
    assert player_vlr_ids["crashies"] == 2002


def test_parse_match_extracts_agent_compositions(scraper):
    """Test that parse_match extracts agent compositions."""
    result = scraper.parse_match(FIXTURE_MATCH_HTML, "https://www.vlr.gg/12345/sen-vs-nrg")

    map1 = result["maps"][0]
    agent_comps = map1["agent_compositions"]

    # Map 1 should have 4 player-agent entries (2 per team in fixture)
    assert len(agent_comps) == 4

    # Check TenZ played Jett
    tenz_entry = next((entry for entry in agent_comps if entry["name"] == "TenZ"), None)
    assert tenz_entry is not None
    assert tenz_entry["agent"] == "jett"
    assert tenz_entry["team"] == "Sentinels"

    # Check FNS played Viper
    fns_entry = next((entry for entry in agent_comps if entry["name"] == "FNS"), None)
    assert fns_entry is not None
    assert fns_entry["agent"] == "viper"
    assert fns_entry["team"] == "NRG"


def test_parse_match_extracts_starting_sides(scraper):
    """Test that parse_match extracts starting sides from round timeline."""
    result = scraper.parse_match(FIXTURE_MATCH_HTML, "https://www.vlr.gg/12345/sen-vs-nrg")

    map1 = result["maps"][0]
    starting_sides = map1["starting_sides"]

    # From fixture: Round 1 shows Sentinels (team1, top) won on attack (mod-t)
    assert starting_sides["team1"] == "attack"
    assert starting_sides["team2"] == "defense"

    # Map 2: Round 1 shows NRG (team2, bottom) won on defense (mod-ct)
    map2 = result["maps"][1]
    starting_sides2 = map2["starting_sides"]
    assert starting_sides2["team1"] == "attack"
    assert starting_sides2["team2"] == "defense"


def test_parse_match_handles_missing_stat_cells(scraper):
    """Test that parse_match handles missing stat cells gracefully."""
    # HTML with incomplete stat row (missing cells)
    incomplete_html = """
    <html>
    <body>
        <div class="match-header">
            <a class="match-header-link"><div class="wf-title-med">Team1</div></a>
            <a class="match-header-link"><div class="wf-title-med">Team2</div></a>
        </div>
        <div class="vm-stats-gamesnav">
            <div class="vm-stats-gamesnav-item" data-game-id="all">All Maps</div>
            <div class="vm-stats-gamesnav-item" data-game-id="123">1Haven</div>
        </div>
        <table class="wf-table-inset mod-overview"><tr><th>Aggregate</th></tr></table>
        <table class="wf-table-inset mod-overview"><tr><th>Aggregate</th></tr></table>
        <table class="wf-table-inset mod-overview">
            <tr>
                <td><a href="/player/999/player1"><div style="font-weight: 700">Player1</div></a></td>
                <td><img title="sage" /></td>
                <td>-</td><td>-</td>
            </tr>
        </table>
        <table class="wf-table-inset mod-overview"><tr><th>Team2</th></tr></table>
        <div class="vlr-rounds"><div class="vlr-rounds-row"><div></div></div></div>
    </body>
    </html>
    """

    # Should not crash, should handle gracefully
    result = scraper.parse_match(incomplete_html, "https://www.vlr.gg/999/test")

    assert result["teams"] == ["Team1", "Team2"]
    # Map should still be present even if stats extraction fails
    assert len(result["maps"]) == 1


def test_parse_match_handles_missing_kast_gracefully(scraper):
    """Test that parse_match handles missing KAST% (None values) gracefully."""
    # HTML with KAST% cell containing '-'
    html_with_missing_kast = """
    <html>
    <body>
        <div class="match-header">
            <a class="match-header-link"><div class="wf-title-med">SEN</div></a>
            <a class="match-header-link"><div class="wf-title-med">NRG</div></a>
        </div>
        <div class="vm-stats-gamesnav">
            <div class="vm-stats-gamesnav-item" data-game-id="all">All</div>
            <div class="vm-stats-gamesnav-item" data-game-id="1">1Lotus</div>
        </div>
        <table class="wf-table-inset mod-overview"><tr><th>All</th></tr></table>
        <table class="wf-table-inset mod-overview"><tr><th>All</th></tr></table>
        <table class="wf-table-inset mod-overview">
            <tr>
                <td><a href="/player/100/test"><div style="font-weight: 700">TestPlayer</div></a></td>
                <td><img title="chamber" /></td>
                <td>1.0</td><td>200</td><td>20</td><td>20</td><td>5</td><td>0</td>
                <td>-</td>
                <td>150</td><td>25</td><td>3</td><td>2</td>
            </tr>
        </table>
        <table class="wf-table-inset mod-overview"><tr><th>NRG</th></tr></table>
        <div class="vlr-rounds"><div class="vlr-rounds-row"><div></div></div></div>
    </body>
    </html>
    """

    result = scraper.parse_match(html_with_missing_kast, "https://www.vlr.gg/999/test")

    map1 = result["maps"][0]
    assert "TestPlayer" in map1["player_stats"]

    # KAST% should be None (not crash)
    assert map1["player_stats"]["TestPlayer"]["kast_pct"] is None

    # Other stats should still be present
    assert map1["player_stats"]["TestPlayer"]["acs"] == 200.0
    assert map1["player_stats"]["TestPlayer"]["kills"] == 20
