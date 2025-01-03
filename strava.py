import requests
import os
import csv
import json
from dotenv import load_dotenv
from datetime import datetime

# Load environment variables from .env file
dotenv_path='../secret/.env'
load_dotenv(dotenv_path=dotenv_path)

# Strava API credentials
STRAVA_CLIENT_ID = os.getenv("STRAVA_CLIENT_ID")
STRAVA_CLIENT_SECRET = os.getenv("STRAVA_CLIENT_SECRET")
STRAVA_REFRESH_TOKEN = os.getenv("STRAVA_REFRESH_TOKEN")
BASE_URL = "https://www.strava.com/api/v3"

print(STRAVA_CLIENT_ID)
# Metadata file and CSV file paths
METADATA_FILE = "activity_metadata.json"
CSV_FILE = "activities.csv"

# Function to get a new access token
def get_access_token():
    url = "https://www.strava.com/oauth/token"
    payload = {
        "client_id": STRAVA_CLIENT_ID,
        "client_secret": STRAVA_CLIENT_SECRET,
        "refresh_token": STRAVA_REFRESH_TOKEN,
        "grant_type": "refresh_token",
    }
    response = requests.post(url, data=payload)
    if response.status_code == 200:
        return response.json()["access_token"]
    else:
        raise Exception(f"Failed to get access token: {response.status_code} {response.text}")

# Load metadata from file
def load_metadata():
    if os.path.exists(METADATA_FILE):
        with open(METADATA_FILE, "r") as f:
            return json.load(f)
    return {"record_count": 0, "last_activity_date": None}

# Save metadata to file
def save_metadata(record_count, last_activity_date):
    metadata = {"record_count": record_count, "last_activity_date": last_activity_date}
    with open(METADATA_FILE, "w") as f:
        json.dump(metadata, f)

# Append activity to CSV dynamically
def append_activity_to_csv(activity):
    # Flatten nested fields and ensure consistent keys
    flattened = {}
    for key, value in activity.items():
        if isinstance(value, dict):  # Flatten nested dictionaries
            for sub_key, sub_value in value.items():
                flattened[f"{key}.{sub_key}"] = sub_value
        elif isinstance(value, list):  # Convert lists to strings
            flattened[key] = str(value)
        else:
            flattened[key] = value

    # Define all possible fields based on Strava API
    required_fields = [
        'resource_state', 'athlete.id', 'athlete.resource_state', 'name', 'distance', 'moving_time',
        'elapsed_time', 'total_elevation_gain', 'type', 'sport_type', 'workout_type', 'id',
        'start_date', 'start_date_local', 'timezone', 'utc_offset', 'location_city',
        'location_state', 'location_country', 'achievement_count', 'kudos_count',
        'comment_count', 'athlete_count', 'photo_count', 'map.id', 'map.summary_polyline',
        'map.resource_state', 'trainer', 'commute', 'manual', 'private', 'visibility',
        'flagged', 'gear_id', 'start_latlng', 'end_latlng', 'average_speed', 'max_speed',
        'average_cadence', 'average_watts', 'max_watts', 'weighted_average_watts', 'device_watts',
        'kilojoules', 'has_heartrate', 'average_heartrate', 'max_heartrate', 'heartrate_opt_out',
        'display_hide_heartrate_option', 'elev_high', 'elev_low', 'upload_id', 'upload_id_str',
        'external_id', 'from_accepted_tag', 'pr_count', 'total_photo_count', 'has_kudoed',
        'suffer_score'
    ]


    # Fill missing fields with None
    for field in required_fields:
        if field not in flattened:
            flattened[field] = None

    file_exists = os.path.isfile(CSV_FILE)
    with open(CSV_FILE, "a", newline="") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=required_fields)
        if not file_exists:
            writer.writeheader()
        writer.writerow({field: flattened.get(field) for field in required_fields})


# Function to retrieve stats
def get_athlete_stats():
    try:
        access_token = get_access_token()
        
        headers = {
            "Authorization": f"Bearer {access_token}"
        }
        response = requests.get(f"{BASE_URL}/athlete", headers=headers)
        if response.status_code == 200:
            athlete_data = response.json()
            print("Athlete Details:")
            print(athlete_data)

            # Get stats for the athlete
            stats_url = f"{BASE_URL}/athletes/{athlete_data['id']}/stats"
            stats_response = requests.get(stats_url, headers=headers)

            if stats_response.status_code == 200:
                stats_data = stats_response.json()
                return stats_data
            else:
                raise Exception(f"Failed to retrieve stats: {stats_response.status_code} {stats_response.text}")
        else:
            raise Exception(f"Failed to retrieve athlete data: {response.status_code} {response.text}")
    except Exception as e:
        print(e)
        return None

# Retrieve activities for 2024
def get_activities_for_2024():
    metadata = load_metadata()
    last_activity_date = metadata.get("last_activity_date")
    #record_count = metadata.get("record_count", 0)
    record_count = 0

    try:
        access_token = get_access_token()
        headers = {"Authorization": f"Bearer {access_token}"}
        activities_url = f"{BASE_URL}/athlete/activities"
        params = {"per_page": 50, "page": 1}
        
        while True:
            response = requests.get(activities_url, headers=headers, params=params)
            if response.status_code == 429:
                print("Rate limit exceeded. Exiting.")
                break

            if response.status_code == 200:
                activities = response.json()
                if not activities:  # No more activities to fetch
                    break

                for activity in activities:
                    activity_date = datetime.strptime(activity["start_date"], "%Y-%m-%dT%H:%M:%SZ")
                    print(activity_date)

                    #if activity_date.year == 2024:
                        #print(f"activity year is {activity_date.year}")
                        # Skip activities already processed
                        #if last_activity_date and activity["start_date"] <= last_activity_date:
                        #    continue
                    #print(activity)
                    append_activity_to_csv(activity)
                    record_count += 1
                    print(f'Record count {record_count}')
                    last_activity_date = activity["start_date"]

                
                params["page"] += 1  # Increment the page for the next request
            else:
                raise Exception(f"Failed to retrieve activities: {response.status_code} {response.text}")

        save_metadata(record_count, last_activity_date)
        print(f"Saved {record_count} activities. Last activity date: {last_activity_date}")
    except Exception as e:
        print(e)


if __name__ == "__main__":
    stats = get_athlete_stats()

    refresh_data = input("Do you want to refresh the data?y/n \n")

    if stats:
        print("Athlete Stats:")
        print(stats)
    else:
        print("Failed to retrieve stats.")
    
    if refresh_data == 'y':
        get_activities_for_2024()
    else:
        print("no updates")
    