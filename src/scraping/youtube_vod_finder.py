"""YouTube Data API v3 integration for VOD discovery and accessibility validation.

Purpose: Find individual map VODs when VLR.gg pages lack per-map links.
Many VLR.gg match pages only link full series VODs or have no links at all.
YouTube API search fills this gap by finding individual map broadcasts.

Requirements:
- YouTube Data API v3 enabled in Google Cloud Console
- YOUTUBE_API_KEY environment variable set
- Quota tracking (10,000 units/day limit)

Quota costs:
- search().list: 100 units per call
- videos().list: 1 unit per call
"""

import os
import re
from typing import Any

import structlog
from googleapiclient.discovery import build

logger = structlog.get_logger(__name__)


class QuotaExhaustedError(Exception):
    """Raised when YouTube API daily quota would be exceeded."""

    def __init__(self, quota_used: int, quota_limit: int):
        self.quota_used = quota_used
        self.quota_limit = quota_limit
        super().__init__(
            f"YouTube API quota exhausted: {quota_used}/{quota_limit} units used"
        )


class YouTubeVODFinder:
    """Find and validate YouTube VODs for VCT matches using YouTube Data API v3.

    Features:
    - Search for map-specific VODs by team names, tournament, map
    - Validate video accessibility (public, processed)
    - Track quota usage (10,000 units/day limit)
    - Prefer VLR.gg URLs when available, fall back to search

    Example:
        >>> finder = YouTubeVODFinder()
        >>> url = finder.find_map_vod(
        ...     teams=["Sentinels", "Fnatic"],
        ...     tournament="VCT Champions",
        ...     map_name="Ascent",
        ...     map_number=1
        ... )
        >>> print(url)  # "https://youtube.com/watch?v=..."
    """

    QUOTA_LIMIT = 10000  # Daily quota limit
    SEARCH_COST = 100  # Cost per search().list call
    VALIDATE_COST = 1  # Cost per videos().list call

    def __init__(self, api_key: str | None = None):
        """Initialize YouTube VOD finder.

        Args:
            api_key: YouTube Data API key. If None, reads from YOUTUBE_API_KEY env var.

        Raises:
            ValueError: If api_key is None and YOUTUBE_API_KEY env var not set.
        """
        if api_key is None:
            api_key = os.environ.get("YOUTUBE_API_KEY")
            if api_key is None:
                raise ValueError(
                    "YouTube API key not provided. Set YOUTUBE_API_KEY environment "
                    "variable or pass api_key parameter."
                )

        self._youtube = build('youtube', 'v3', developerKey=api_key)
        self.quota_used = 0
        self._log = logger.bind(component="youtube_vod_finder")

    @property
    def quota_remaining(self) -> int:
        """Return remaining quota units."""
        return self.QUOTA_LIMIT - self.quota_used

    def _check_quota(self, cost: int) -> None:
        """Check if operation would exceed quota limit.

        Args:
            cost: Quota cost of the operation

        Raises:
            QuotaExhaustedError: If operation would exceed daily quota
        """
        if self.quota_used + cost > self.QUOTA_LIMIT:
            raise QuotaExhaustedError(self.quota_used, self.QUOTA_LIMIT)

    def extract_video_id(self, url: str) -> str | None:
        """Extract video ID from YouTube URL.

        Handles formats:
        - youtube.com/watch?v=VIDEO_ID
        - youtu.be/VIDEO_ID
        - youtube.com/embed/VIDEO_ID

        Args:
            url: YouTube URL

        Returns:
            Video ID string or None if not a valid YouTube URL
        """
        # Match youtube.com/watch?v=ID
        match = re.search(r'(?:youtube\.com/watch\?v=)([a-zA-Z0-9_-]+)', url)
        if match:
            return match.group(1)

        # Match youtu.be/ID
        match = re.search(r'(?:youtu\.be/)([a-zA-Z0-9_-]+)', url)
        if match:
            return match.group(1)

        # Match youtube.com/embed/ID
        match = re.search(r'(?:youtube\.com/embed/)([a-zA-Z0-9_-]+)', url)
        if match:
            return match.group(1)

        return None

    def validate_video(self, video_id: str) -> bool:
        """Validate that a video is accessible for download.

        Checks:
        - Privacy status is "public"
        - Upload status is "processed"

        Note: We don't check embeddable status because we download videos
        via yt-dlp, not embed them.

        Args:
            video_id: YouTube video ID

        Returns:
            True if video is public and processed, False otherwise
        """
        self._check_quota(self.VALIDATE_COST)
        # Consume quota before making the call (it's consumed regardless of success/failure)
        self.quota_used += self.VALIDATE_COST

        try:
            response = self._youtube.videos().list(
                part="status",
                id=video_id
            ).execute()

            if not response.get("items"):
                self._log.warning("video_not_found", video_id=video_id)
                return False

            status = response["items"][0]["status"]
            privacy_status = status.get("privacyStatus", "")
            upload_status = status.get("uploadStatus", "")

            is_valid = (
                privacy_status == "public" and
                upload_status == "processed"
            )

            self._log.debug(
                "video_validation",
                video_id=video_id,
                privacy=privacy_status,
                upload=upload_status,
                valid=is_valid
            )

            return is_valid

        except Exception as e:
            self._log.error("validate_error", video_id=video_id, error=str(e))
            return False

    def find_map_vod(
        self,
        teams: list[str],
        tournament: str,
        map_name: str,
        date: str | None = None,
        map_number: int | None = None
    ) -> str | None:
        """Search YouTube for a map-specific VOD.

        Constructs search query from teams, tournament, map name, and optional map number.
        Filters for long videos (>20min) to exclude highlights/clips.
        Validates accessibility of results and returns first accessible video.

        Args:
            teams: List of team names (e.g., ["Sentinels", "Fnatic"])
            tournament: Tournament name (e.g., "VCT Champions")
            map_name: Map name (e.g., "Ascent")
            date: Match date in YYYY-MM-DD format (optional, for date filtering)
            map_number: Map number in series (optional, appended to query)

        Returns:
            YouTube URL of first accessible video, or None if no accessible videos found

        Raises:
            QuotaExhaustedError: If search would exceed daily quota
        """
        self._check_quota(self.SEARCH_COST)

        # Construct search query
        query_parts = [
            f"{teams[0]} vs {teams[1]}",
            map_name,
            tournament
        ]
        if map_number is not None:
            query_parts.append(f"Map {map_number}")

        query = " ".join(query_parts)

        # Build search parameters
        search_params: dict[str, Any] = {
            "q": query,
            "part": "id,snippet",
            "type": "video",
            "maxResults": 5,
            "videoDuration": "long"  # >20min (filters out highlights/clips)
        }

        # Add date filtering if provided
        if date:
            # Parse date and create window: [date-7days, date+30days]
            from datetime import datetime, timedelta
            match_date = datetime.strptime(date, "%Y-%m-%d")
            published_after = (match_date - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")
            published_before = (match_date + timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")

            search_params["publishedAfter"] = published_after
            search_params["publishedBefore"] = published_before

        try:
            # Execute search
            response = self._youtube.search().list(**search_params).execute()
            self.quota_used += self.SEARCH_COST

            items = response.get("items", [])
            accessible_count = 0

            # Validate each result
            for item in items:
                video_id = item["id"]["videoId"]
                if self.validate_video(video_id):
                    accessible_count += 1
                    video_url = f"https://youtube.com/watch?v={video_id}"
                    self._log.info(
                        "youtube_search_success",
                        query=query,
                        total_results=len(items),
                        accessible_count=accessible_count,
                        video_url=video_url
                    )
                    return video_url

            # No accessible videos found
            self._log.info(
                "youtube_search_no_accessible",
                query=query,
                total_results=len(items),
                accessible_count=0
            )
            return None

        except Exception as e:
            self._log.error("search_error", query=query, error=str(e))
            return None

    def find_vods_for_match(self, match_data: dict) -> dict[int, str | None]:
        """Find VODs for all maps in a match.

        Prefers VLR.gg URLs when available and valid.
        Falls back to YouTube search when VLR.gg URL is missing or inaccessible.

        Args:
            match_data: Match data dict from VLRMatchScraper.parse_match
                Expected keys: teams, tournament, maps
                Each map dict should have: map_name, map_number, vod_url (optional)

        Returns:
            Dict mapping map_number -> youtube_url (or None if not found)

        Example:
            >>> match_data = {
            ...     "teams": ["Sentinels", "Fnatic"],
            ...     "tournament": "VCT Champions",
            ...     "maps": [
            ...         {"map_number": 1, "map_name": "Ascent", "vod_url": None},
            ...         {"map_number": 2, "map_name": "Bind", "vod_url": "https://youtube.com/..."}
            ...     ]
            ... }
            >>> vods = finder.find_vods_for_match(match_data)
            >>> print(vods)  # {1: "https://youtube.com/...", 2: "https://youtube.com/..."}
        """
        teams = match_data["teams"]
        tournament = match_data.get("tournament", "")
        maps = match_data.get("maps", [])
        date = match_data.get("date")

        vods: dict[int, str | None] = {}
        found_count = 0

        for map_data in maps:
            map_number = map_data["map_number"]
            map_name = map_data["map_name"]
            vlr_vod_url = map_data.get("vod_url")

            vod_url = None

            # First, try VLR.gg URL if available
            if vlr_vod_url:
                video_id = self.extract_video_id(vlr_vod_url)
                if video_id and self.validate_video(video_id):
                    vod_url = vlr_vod_url
                    self._log.debug(
                        "vlr_vod_valid",
                        map_number=map_number,
                        url=vod_url
                    )
                else:
                    self._log.debug(
                        "vlr_vod_invalid",
                        map_number=map_number,
                        url=vlr_vod_url
                    )

            # Fall back to YouTube search if VLR URL missing or invalid
            if vod_url is None:
                vod_url = self.find_map_vod(
                    teams=teams,
                    tournament=tournament,
                    map_name=map_name,
                    date=date,
                    map_number=map_number
                )

            vods[map_number] = vod_url
            if vod_url is not None:
                found_count += 1

        self._log.info(
            "match_vods_found",
            teams=f"{teams[0]} vs {teams[1]}",
            found=found_count,
            total=len(maps)
        )

        return vods
