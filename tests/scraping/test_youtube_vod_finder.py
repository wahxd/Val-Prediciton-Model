"""Tests for YouTube VOD finder."""

from unittest.mock import MagicMock, Mock, patch

import pytest

from src.scraping.youtube_vod_finder import QuotaExhaustedError, YouTubeVODFinder


@pytest.fixture
def mock_youtube_service():
    """Create a mock YouTube API service."""
    service = MagicMock()
    return service


@pytest.fixture
def finder(mock_youtube_service):
    """Create YouTubeVODFinder with mocked API."""
    with patch('src.scraping.youtube_vod_finder.build', return_value=mock_youtube_service):
        finder = YouTubeVODFinder(api_key="test_key")
    return finder


class TestInitialization:
    """Test YouTubeVODFinder initialization."""

    def test_init_with_api_key(self):
        """Test initialization with explicit API key."""
        with patch('src.scraping.youtube_vod_finder.build') as mock_build:
            finder = YouTubeVODFinder(api_key="explicit_key")
            mock_build.assert_called_once_with('youtube', 'v3', developerKey="explicit_key")
            assert finder.quota_used == 0

    def test_init_from_env_var(self, monkeypatch):
        """Test initialization from YOUTUBE_API_KEY env var."""
        monkeypatch.setenv("YOUTUBE_API_KEY", "env_key")
        with patch('src.scraping.youtube_vod_finder.build') as mock_build:
            finder = YouTubeVODFinder()
            mock_build.assert_called_once_with('youtube', 'v3', developerKey="env_key")

    def test_init_missing_api_key(self, monkeypatch):
        """Test initialization fails when API key not provided."""
        monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)
        with pytest.raises(ValueError, match="YouTube API key not provided"):
            YouTubeVODFinder()


class TestExtractVideoId:
    """Test video ID extraction from URLs."""

    def test_extract_watch_url(self, finder):
        """Test extraction from youtube.com/watch?v=ID format."""
        url = "https://youtube.com/watch?v=dQw4w9WgXcQ"
        assert finder.extract_video_id(url) == "dQw4w9WgXcQ"

    def test_extract_watch_url_with_params(self, finder):
        """Test extraction from watch URL with additional parameters."""
        url = "https://youtube.com/watch?v=dQw4w9WgXcQ&t=123s"
        assert finder.extract_video_id(url) == "dQw4w9WgXcQ"

    def test_extract_short_url(self, finder):
        """Test extraction from youtu.be/ID format."""
        url = "https://youtu.be/dQw4w9WgXcQ"
        assert finder.extract_video_id(url) == "dQw4w9WgXcQ"

    def test_extract_embed_url(self, finder):
        """Test extraction from youtube.com/embed/ID format."""
        url = "https://youtube.com/embed/dQw4w9WgXcQ"
        assert finder.extract_video_id(url) == "dQw4w9WgXcQ"

    def test_extract_invalid_url(self, finder):
        """Test extraction from non-YouTube URL."""
        url = "https://vimeo.com/12345"
        assert finder.extract_video_id(url) is None


class TestValidateVideo:
    """Test video accessibility validation."""

    def test_validate_public_processed_video(self, finder, mock_youtube_service):
        """Test validation of accessible video."""
        # Mock API response
        mock_videos = MagicMock()
        mock_list = MagicMock()
        mock_execute = MagicMock()

        mock_execute.return_value = {
            "items": [{
                "status": {
                    "privacyStatus": "public",
                    "uploadStatus": "processed"
                }
            }]
        }
        mock_list.return_value.execute = mock_execute
        mock_videos.return_value.list = mock_list
        mock_youtube_service.videos = mock_videos

        assert finder.validate_video("test_id") is True
        assert finder.quota_used == 1

    def test_validate_private_video(self, finder, mock_youtube_service):
        """Test validation of private video."""
        mock_videos = MagicMock()
        mock_list = MagicMock()
        mock_execute = MagicMock()

        mock_execute.return_value = {
            "items": [{
                "status": {
                    "privacyStatus": "private",
                    "uploadStatus": "processed"
                }
            }]
        }
        mock_list.return_value.execute = mock_execute
        mock_videos.return_value.list = mock_list
        mock_youtube_service.videos = mock_videos

        assert finder.validate_video("test_id") is False
        assert finder.quota_used == 1

    def test_validate_unprocessed_video(self, finder, mock_youtube_service):
        """Test validation of unprocessed video."""
        mock_videos = MagicMock()
        mock_list = MagicMock()
        mock_execute = MagicMock()

        mock_execute.return_value = {
            "items": [{
                "status": {
                    "privacyStatus": "public",
                    "uploadStatus": "uploading"
                }
            }]
        }
        mock_list.return_value.execute = mock_execute
        mock_videos.return_value.list = mock_list
        mock_youtube_service.videos = mock_videos

        assert finder.validate_video("test_id") is False
        assert finder.quota_used == 1

    def test_validate_nonexistent_video(self, finder, mock_youtube_service):
        """Test validation of nonexistent video."""
        mock_videos = MagicMock()
        mock_list = MagicMock()
        mock_execute = MagicMock()

        mock_execute.return_value = {"items": []}
        mock_list.return_value.execute = mock_execute
        mock_videos.return_value.list = mock_list
        mock_youtube_service.videos = mock_videos

        assert finder.validate_video("nonexistent") is False
        assert finder.quota_used == 1

    def test_validate_api_error(self, finder, mock_youtube_service):
        """Test validation handles API errors gracefully."""
        mock_videos = MagicMock()
        mock_list = MagicMock()

        mock_list.return_value.execute.side_effect = Exception("API error")
        mock_videos.return_value.list = mock_list
        mock_youtube_service.videos = mock_videos

        assert finder.validate_video("test_id") is False
        # Quota still consumed even on error
        assert finder.quota_used == 1


class TestFindMapVod:
    """Test YouTube search for map VODs."""

    def test_find_map_vod_success(self, finder, mock_youtube_service):
        """Test successful map VOD search."""
        # Mock search response
        mock_search_list_obj = MagicMock()
        mock_search_list_obj.execute.return_value = {
            "items": [
                {"id": {"videoId": "video1"}},
                {"id": {"videoId": "video2"}}
            ]
        }
        mock_youtube_service.search().list.return_value = mock_search_list_obj

        # Mock videos validation (first video is private, second is public)
        validation_results = {
            "video1": {
                "items": [{
                    "status": {"privacyStatus": "private", "uploadStatus": "processed"}
                }]
            },
            "video2": {
                "items": [{
                    "status": {"privacyStatus": "public", "uploadStatus": "processed"}
                }]
            }
        }

        def videos_list_side_effect(**kwargs):
            video_id = kwargs.get('id', '')
            mock_execute = MagicMock()
            mock_execute.execute.return_value = validation_results.get(video_id, {"items": []})
            return mock_execute

        mock_youtube_service.videos().list.side_effect = videos_list_side_effect

        url = finder.find_map_vod(
            teams=["Sentinels", "Fnatic"],
            tournament="VCT Champions",
            map_name="Ascent",
            map_number=1
        )

        assert url == "https://youtube.com/watch?v=video2"
        # 100 for search + 1 for video1 validation + 1 for video2 validation
        assert finder.quota_used == 102

    def test_find_map_vod_no_results(self, finder, mock_youtube_service):
        """Test search with no results."""
        mock_search = MagicMock()
        mock_search_list = MagicMock()
        mock_search_execute = MagicMock()

        mock_search_execute.return_value = {"items": []}
        mock_search_list.return_value.execute = mock_search_execute
        mock_search.return_value.list = mock_search_list
        mock_youtube_service.search = mock_search

        url = finder.find_map_vod(
            teams=["Team1", "Team2"],
            tournament="Tournament",
            map_name="Map"
        )

        assert url is None
        assert finder.quota_used == 100  # Only search cost

    def test_find_map_vod_all_private(self, finder, mock_youtube_service):
        """Test search where all videos are private."""
        # Mock search response
        mock_search = MagicMock()
        mock_search_list = MagicMock()
        mock_search_execute = MagicMock()

        mock_search_execute.return_value = {
            "items": [{"id": {"videoId": "video1"}}]
        }
        mock_search_list.return_value.execute = mock_search_execute
        mock_search.return_value.list = mock_search_list
        mock_youtube_service.search = mock_search

        # Mock video as private
        mock_videos = MagicMock()
        mock_videos_list = MagicMock()
        mock_videos_execute = MagicMock()

        mock_videos_execute.return_value = {
            "items": [{
                "status": {"privacyStatus": "private", "uploadStatus": "processed"}
            }]
        }
        mock_videos_list.return_value.execute = mock_videos_execute
        mock_videos.return_value.list = mock_videos_list
        mock_youtube_service.videos = mock_videos

        url = finder.find_map_vod(
            teams=["Team1", "Team2"],
            tournament="Tournament",
            map_name="Map"
        )

        assert url is None
        assert finder.quota_used == 101  # 100 search + 1 validate

    def test_find_map_vod_with_date_filter(self, finder, mock_youtube_service):
        """Test search with date filtering."""
        mock_search = MagicMock()
        mock_search_list = MagicMock()
        mock_search_execute = MagicMock()

        mock_search_execute.return_value = {"items": []}
        mock_search_list.return_value.execute = mock_search_execute
        mock_search.return_value.list = mock_search_list
        mock_youtube_service.search = mock_search

        finder.find_map_vod(
            teams=["Team1", "Team2"],
            tournament="Tournament",
            map_name="Map",
            date="2024-03-15"
        )

        # Verify publishedAfter and publishedBefore were set
        call_kwargs = mock_search_list.call_args[1]
        assert "publishedAfter" in call_kwargs
        assert "publishedBefore" in call_kwargs
        assert "2024-03-08" in call_kwargs["publishedAfter"]  # 7 days before
        assert "2024-04-14" in call_kwargs["publishedBefore"]  # 30 days after

    def test_find_map_vod_constructs_correct_query(self, finder, mock_youtube_service):
        """Test search query construction."""
        mock_search = MagicMock()
        mock_search_list = MagicMock()
        mock_search_execute = MagicMock()

        mock_search_execute.return_value = {"items": []}
        mock_search_list.return_value.execute = mock_search_execute
        mock_search.return_value.list = mock_search_list
        mock_youtube_service.search = mock_search

        finder.find_map_vod(
            teams=["Sentinels", "Fnatic"],
            tournament="VCT Champions",
            map_name="Ascent",
            map_number=2
        )

        call_kwargs = mock_search_list.call_args[1]
        assert call_kwargs["q"] == "Sentinels vs Fnatic Ascent VCT Champions Map 2"
        assert call_kwargs["videoDuration"] == "long"
        assert call_kwargs["maxResults"] == 5


class TestQuotaManagement:
    """Test quota tracking and limits."""

    def test_quota_remaining(self, finder):
        """Test quota_remaining property."""
        assert finder.quota_remaining == 10000
        finder.quota_used = 5000
        assert finder.quota_remaining == 5000

    def test_quota_exhausted_on_search(self, finder):
        """Test QuotaExhaustedError raised when search would exceed quota."""
        finder.quota_used = 9950  # 50 units remaining

        with pytest.raises(QuotaExhaustedError) as exc_info:
            finder.find_map_vod(
                teams=["Team1", "Team2"],
                tournament="Tournament",
                map_name="Map"
            )

        assert exc_info.value.quota_used == 9950
        assert exc_info.value.quota_limit == 10000
        assert "9950/10000" in str(exc_info.value)

    def test_quota_exhausted_on_validate(self, finder, mock_youtube_service):
        """Test QuotaExhaustedError raised when validate would exceed quota."""
        finder.quota_used = 9999  # 1 unit remaining

        # First validation should succeed
        mock_videos = MagicMock()
        mock_list = MagicMock()
        mock_execute = MagicMock()

        mock_execute.return_value = {
            "items": [{
                "status": {"privacyStatus": "public", "uploadStatus": "processed"}
            }]
        }
        mock_list.return_value.execute = mock_execute
        mock_videos.return_value.list = mock_list
        mock_youtube_service.videos = mock_videos

        assert finder.validate_video("test_id") is True
        assert finder.quota_used == 10000

        # Second validation should raise
        with pytest.raises(QuotaExhaustedError):
            finder.validate_video("test_id2")

    def test_quota_tracking_increments(self, finder, mock_youtube_service):
        """Test quota increments correctly for search and validate."""
        # Mock search
        mock_search = MagicMock()
        mock_search_list = MagicMock()
        mock_search_execute = MagicMock()

        mock_search_execute.return_value = {
            "items": [{"id": {"videoId": "video1"}}]
        }
        mock_search_list.return_value.execute = mock_search_execute
        mock_search.return_value.list = mock_search_list
        mock_youtube_service.search = mock_search

        # Mock video validation
        mock_videos = MagicMock()
        mock_videos_list = MagicMock()
        mock_videos_execute = MagicMock()

        mock_videos_execute.return_value = {
            "items": [{
                "status": {"privacyStatus": "public", "uploadStatus": "processed"}
            }]
        }
        mock_videos_list.return_value.execute = mock_videos_execute
        mock_videos.return_value.list = mock_videos_list
        mock_youtube_service.videos = mock_videos

        finder.find_map_vod(
            teams=["Team1", "Team2"],
            tournament="Tournament",
            map_name="Map"
        )

        # 100 for search + 1 for validation
        assert finder.quota_used == 101


class TestFindVodsForMatch:
    """Test finding VODs for all maps in a match."""

    def test_find_vods_prefers_vlr_urls(self, finder, mock_youtube_service):
        """Test that VLR.gg URLs are preferred when valid."""
        # Mock video validation
        mock_videos = MagicMock()
        mock_videos_list = MagicMock()
        mock_videos_execute = MagicMock()

        mock_videos_execute.return_value = {
            "items": [{
                "status": {"privacyStatus": "public", "uploadStatus": "processed"}
            }]
        }
        mock_videos_list.return_value.execute = mock_videos_execute
        mock_videos.return_value.list = mock_videos_list
        mock_youtube_service.videos = mock_videos

        match_data = {
            "teams": ["Team1", "Team2"],
            "tournament": "Tournament",
            "maps": [
                {
                    "map_number": 1,
                    "map_name": "Ascent",
                    "vod_url": "https://youtube.com/watch?v=vlr_video"
                }
            ]
        }

        vods = finder.find_vods_for_match(match_data)

        assert vods == {1: "https://youtube.com/watch?v=vlr_video"}
        # Only 1 validation call, no search
        assert finder.quota_used == 1

    def test_find_vods_falls_back_to_search(self, finder, mock_youtube_service):
        """Test fallback to YouTube search when VLR.gg URL missing."""
        # Mock search
        mock_search = MagicMock()
        mock_search_list = MagicMock()
        mock_search_execute = MagicMock()

        mock_search_execute.return_value = {
            "items": [{"id": {"videoId": "search_video"}}]
        }
        mock_search_list.return_value.execute = mock_search_execute
        mock_search.return_value.list = mock_search_list
        mock_youtube_service.search = mock_search

        # Mock video validation
        mock_videos = MagicMock()
        mock_videos_list = MagicMock()
        mock_videos_execute = MagicMock()

        mock_videos_execute.return_value = {
            "items": [{
                "status": {"privacyStatus": "public", "uploadStatus": "processed"}
            }]
        }
        mock_videos_list.return_value.execute = mock_videos_execute
        mock_videos.return_value.list = mock_videos_list
        mock_youtube_service.videos = mock_videos

        match_data = {
            "teams": ["Team1", "Team2"],
            "tournament": "Tournament",
            "maps": [
                {
                    "map_number": 1,
                    "map_name": "Ascent",
                    "vod_url": None
                }
            ]
        }

        vods = finder.find_vods_for_match(match_data)

        assert vods == {1: "https://youtube.com/watch?v=search_video"}
        # 100 for search + 1 for validation
        assert finder.quota_used == 101

    def test_find_vods_invalid_vlr_url_fallback(self, finder, mock_youtube_service):
        """Test fallback to search when VLR.gg URL is invalid."""
        # First call to validate_video (VLR URL) returns False
        # Second call (from search) returns True
        mock_videos = MagicMock()
        mock_videos_list = MagicMock()

        validate_call_count = [0]

        def videos_execute_side_effect(*args, **kwargs):
            validate_call_count[0] += 1
            if validate_call_count[0] == 1:
                # VLR URL is private
                return {
                    "items": [{
                        "status": {"privacyStatus": "private", "uploadStatus": "processed"}
                    }]
                }
            else:
                # Search result is public
                return {
                    "items": [{
                        "status": {"privacyStatus": "public", "uploadStatus": "processed"}
                    }]
                }

        mock_videos_list.return_value.execute.side_effect = videos_execute_side_effect
        mock_videos.return_value.list = mock_videos_list
        mock_youtube_service.videos = mock_videos

        # Mock search
        mock_search = MagicMock()
        mock_search_list = MagicMock()
        mock_search_execute = MagicMock()

        mock_search_execute.return_value = {
            "items": [{"id": {"videoId": "search_video"}}]
        }
        mock_search_list.return_value.execute = mock_search_execute
        mock_search.return_value.list = mock_search_list
        mock_youtube_service.search = mock_search

        match_data = {
            "teams": ["Team1", "Team2"],
            "tournament": "Tournament",
            "maps": [
                {
                    "map_number": 1,
                    "map_name": "Ascent",
                    "vod_url": "https://youtube.com/watch?v=invalid_video"
                }
            ]
        }

        vods = finder.find_vods_for_match(match_data)

        assert vods == {1: "https://youtube.com/watch?v=search_video"}
        # 1 for VLR validation + 100 for search + 1 for search result validation
        assert finder.quota_used == 102

    def test_find_vods_multiple_maps(self, finder, mock_youtube_service):
        """Test finding VODs for multiple maps."""
        # Mock video validation
        mock_videos = MagicMock()
        mock_videos_list = MagicMock()
        mock_videos_execute = MagicMock()

        mock_videos_execute.return_value = {
            "items": [{
                "status": {"privacyStatus": "public", "uploadStatus": "processed"}
            }]
        }
        mock_videos_list.return_value.execute = mock_videos_execute
        mock_videos.return_value.list = mock_videos_list
        mock_youtube_service.videos = mock_videos

        # Mock search
        mock_search = MagicMock()
        mock_search_list = MagicMock()

        search_call_count = [0]

        def search_execute_side_effect(*args, **kwargs):
            search_call_count[0] += 1
            return {
                "items": [{"id": {"videoId": f"search_video_{search_call_count[0]}"}}]
            }

        mock_search_list.return_value.execute.side_effect = search_execute_side_effect
        mock_search.return_value.list = mock_search_list
        mock_youtube_service.search = mock_search

        match_data = {
            "teams": ["Team1", "Team2"],
            "tournament": "Tournament",
            "maps": [
                {"map_number": 1, "map_name": "Ascent", "vod_url": None},
                {"map_number": 2, "map_name": "Bind", "vod_url": "https://youtube.com/watch?v=vlr_video"},
                {"map_number": 3, "map_name": "Haven", "vod_url": None}
            ]
        }

        vods = finder.find_vods_for_match(match_data)

        assert vods == {
            1: "https://youtube.com/watch?v=search_video_1",
            2: "https://youtube.com/watch?v=vlr_video",
            3: "https://youtube.com/watch?v=search_video_2"
        }
        # Map 1: 100 search + 1 validate
        # Map 2: 1 validate (VLR URL)
        # Map 3: 100 search + 1 validate
        # Total: 203
        assert finder.quota_used == 203

    def test_find_vods_returns_none_when_not_found(self, finder, mock_youtube_service):
        """Test that None is returned for maps without accessible VODs."""
        # Mock search with no results
        mock_search = MagicMock()
        mock_search_list = MagicMock()
        mock_search_execute = MagicMock()

        mock_search_execute.return_value = {"items": []}
        mock_search_list.return_value.execute = mock_search_execute
        mock_search.return_value.list = mock_search_list
        mock_youtube_service.search = mock_search

        match_data = {
            "teams": ["Team1", "Team2"],
            "tournament": "Tournament",
            "maps": [
                {"map_number": 1, "map_name": "Ascent", "vod_url": None}
            ]
        }

        vods = finder.find_vods_for_match(match_data)

        assert vods == {1: None}
        assert finder.quota_used == 100  # Only search cost
