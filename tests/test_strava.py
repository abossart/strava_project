import pytest
import json
import os
import pandas as pd
from unittest.mock import MagicMock, patch, mock_open
import sys

# Add parent directory to path to import strava
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import strava

# --- Metadata Tests ---

def test_load_metadata_file_exists():
    mock_data = '{"record_count": 10, "last_activity_date": "2024-01-01T00:00:00Z"}'
    with patch("builtins.open", mock_open(read_data=mock_data)):
        with patch("os.path.exists", return_value=True):
            metadata = strava.load_metadata()
            assert metadata["record_count"] == 10
            assert metadata["last_activity_date"] == "2024-01-01T00:00:00Z"

def test_load_metadata_file_missing():
    with patch("os.path.exists", return_value=False):
        metadata = strava.load_metadata()
        assert metadata["record_count"] == 0
        assert metadata["last_activity_date"] is None

def test_save_metadata():
    with patch("builtins.open", mock_open()) as mock_file:
        strava.save_metadata(100, "2024-12-31T00:00:00Z")
        mock_file.assert_called_with(strava.METADATA_FILE, "w")
        
        # Verify the content written
        handle = mock_file()
        # We combine the write calls to check the full JSON
        written_content = "".join(call.args[0] for call in handle.write.mock_calls)
        assert '"record_count": 100' in written_content
        assert '"last_activity_date": "2024-12-31T00:00:00Z"' in written_content

# --- Authentication Tests ---

@patch("strava.requests.post")
def test_get_strava_session_success(mock_post):
    # Mock successful token retrieval
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"access_token": "fake_token"}
    mock_post.return_value = mock_response

    session = strava.get_strava_session()
    
    assert session.headers["Authorization"] == "Bearer fake_token"
    mock_post.assert_called_once()

@patch("strava.requests.post")
def test_get_strava_session_failure(mock_post):
    # Mock failed token retrieval
    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.text = "Bad Request"
    mock_post.return_value = mock_response

    with pytest.raises(Exception) as excinfo:
        strava.get_strava_session()
    assert "Failed to get access token" in str(excinfo.value)

# --- Stats Tests ---

@patch("strava.get_strava_session")
def test_get_athlete_stats(mock_get_session):
    mock_session = MagicMock()
    mock_get_session.return_value = mock_session
    
    # Mock calls: 1. Athlete Profile, 2. Stats
    mock_response_profile = MagicMock()
    mock_response_profile.status_code = 200
    mock_response_profile.json.return_value = {"id": 12345}
    
    mock_response_stats = MagicMock()
    mock_response_stats.status_code = 200
    mock_response_stats.json.return_value = {"biggest_ride_distance": 1000}
    
    mock_session.get.side_effect = [mock_response_profile, mock_response_stats]

    stats = strava.get_athlete_stats()
    assert stats["biggest_ride_distance"] == 1000

# --- Activity Fetching Tests ---

@patch("strava.get_strava_session")
@patch("strava.load_metadata")
@patch("strava.save_metadata")
@patch("strava.pd.DataFrame.to_csv") # Mock CSV writing
def test_fetch_new_activities_pagination(mock_to_csv, mock_save, mock_load, mock_get_session):
    # Setup metadata
    mock_load.return_value = {"record_count": 0, "last_activity_date": None}
    
    mock_session = MagicMock()
    mock_get_session.return_value = mock_session

    # Create fake activities
    page1 = [{"id": i, "start_date": f"2024-01-0{i}T00:00:00Z"} for i in range(1, 3)] # 2 activities
    page2 = [] # End of list

    # Mock API responses
    resp1 = MagicMock(); resp1.status_code = 200; resp1.json.return_value = page1
    resp2 = MagicMock(); resp2.status_code = 200; resp2.json.return_value = page2
    
    mock_session.get.side_effect = [resp1, resp2]

    strava.fetch_new_activities()

    # Verify save_metadata was called with correct count (2) and date (newest is 2024-01-01)
    # Note: In our loop, we append page1[0] first, which is id=1, date=...01
    # Actually, the loop appends in order. The newest date depends on the API order.
    # Assuming API returns newest first (standard), page1[0] is newest.
    
    assert mock_save.called
    args, _ = mock_save.call_args
    assert args[0] == 2 # record count
    assert args[1] == "2024-01-01T00:00:00Z" # date of first item

@patch("strava.get_strava_session")
@patch("strava.load_metadata")
@patch("strava.save_metadata")
def test_fetch_new_activities_stops_at_date(mock_save, mock_load, mock_get_session):
    # Setup metadata: Last activity was yesterday
    mock_load.return_value = {"record_count": 10, "last_activity_date": "2024-01-02T00:00:00Z"}
    
    mock_session = MagicMock()
    mock_get_session.return_value = mock_session

    # API returns: [Today, Yesterday, DayBefore]
    # Should process Today, see Yesterday and STOP.
    activities = [
        {"id": 3, "start_date": "2024-01-03T00:00:00Z"}, # New
        {"id": 2, "start_date": "2024-01-02T00:00:00Z"}, # Old (match)
        {"id": 1, "start_date": "2024-01-01T00:00:00Z"}, # Old (shouldn't be reached/processed)
    ]

    resp = MagicMock(); resp.status_code = 200; resp.json.return_value = activities
    mock_session.get.return_value = resp

    with patch("strava.pd.DataFrame.to_csv") as mock_to_csv:
        strava.fetch_new_activities()
        
        # Should have saved 1 activity (id 3)
        # Check the dataframe passed to to_csv
        # It's hard to inspect the DF directly in mock call args without more complex logic,
        # but we can check save_metadata count
        
        args, _ = mock_save.call_args
        # Initial 10 + 1 new = 11
        assert args[0] == 11 
        assert args[1] == "2024-01-03T00:00:00Z"

@patch("strava.get_strava_session")
@patch("strava.load_metadata")
def test_rate_limit_handling(mock_load, mock_get_session):
    mock_load.return_value = {"record_count": 0, "last_activity_date": None}
    mock_session = MagicMock()
    mock_get_session.return_value = mock_session

    # Return 429
    resp = MagicMock(); resp.status_code = 429
    mock_session.get.return_value = resp

    # Should print message and exit loop, NOT raise exception
    with patch("builtins.print") as mock_print:
        strava.fetch_new_activities()
        mock_print.assert_any_call("Rate limit exceeded. Exiting.")
