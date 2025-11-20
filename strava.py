import requests
import os
import json
import pandas as pd
from dotenv import load_dotenv
from datetime import datetime

# Load environment variables from .env file
dotenv_path = '../secret/.env'
load_dotenv(dotenv_path=dotenv_path)

# Strava API credentials
STRAVA_CLIENT_ID = os.getenv("STRAVA_CLIENT_ID")
STRAVA_CLIENT_SECRET = os.getenv("STRAVA_CLIENT_SECRET")
STRAVA_REFRESH_TOKEN = os.getenv("STRAVA_REFRESH_TOKEN")
BASE_URL = "https://www.strava.com/api/v3"

# Metadata file and CSV file paths
METADATA_FILE = "activity_metadata.json"
CSV_FILE = "activities.csv"

def get_strava_session():
    """
    Creates a requests.Session with the access token header.
    """
    url = "https://www.strava.com/oauth/token"
    payload = {
        "client_id": STRAVA_CLIENT_ID,
        "client_secret": STRAVA_CLIENT_SECRET,
        "refresh_token": STRAVA_REFRESH_TOKEN,
        "grant_type": "refresh_token",
    }
    
    response = requests.post(url, data=payload)
    if response.status_code == 200:
        access_token = response.json()["access_token"]
        session = requests.Session()
        session.headers.update({"Authorization": f"Bearer {access_token}"})
        return session
    else:
        raise Exception(f"Failed to get access token: {response.status_code} {response.text}")

def load_metadata():
    if os.path.exists(METADATA_FILE):
        with open(METADATA_FILE, "r") as f:
            return json.load(f)
    return {"record_count": 0, "last_activity_date": None}

def save_metadata(record_count, last_activity_date):
    metadata = {"record_count": record_count, "last_activity_date": last_activity_date}
    with open(METADATA_FILE, "w") as f:
        json.dump(metadata, f)

def get_athlete_stats():
    try:
        session = get_strava_session()
        
        response = session.get(f"{BASE_URL}/athlete")
        if response.status_code == 200:
            athlete_data = response.json()
            print("Athlete Details:")
            print(athlete_data)

            # Get stats for the athlete
            stats_url = f"{BASE_URL}/athletes/{athlete_data['id']}/stats"
            stats_response = session.get(stats_url)

            if stats_response.status_code == 200:
                return stats_response.json()
            else:
                raise Exception(f"Failed to retrieve stats: {stats_response.status_code} {stats_response.text}")
        else:
            raise Exception(f"Failed to retrieve athlete data: {response.status_code} {response.text}")
    except Exception as e:
        print(e)
        return None

def fetch_new_activities():
    metadata = load_metadata()
    last_activity_date = metadata.get("last_activity_date")
    total_record_count = metadata.get("record_count", 0)
    
    new_activities = []
    
    try:
        session = get_strava_session()
        activities_url = f"{BASE_URL}/athlete/activities"
        params = {"per_page": 50, "page": 1}
        
        # If we have a last activity date, we can use 'after' parameter if we were fetching chronologically,
        # but Strava API default is reverse chronological (newest first).
        # So we fetch pages until we hit a date <= last_activity_date.
        
        print("Fetching activities...")
        while True:
            response = session.get(activities_url, params=params)
            
            if response.status_code == 429:
                print("Rate limit exceeded. Exiting.")
                break

            if response.status_code == 200:
                activities = response.json()
                if not activities:
                    break

                stop_fetching = False
                for activity in activities:
                    # Check if we've reached already processed activities
                    # Note: String comparison works for ISO format dates
                    if last_activity_date and activity["start_date"] <= last_activity_date:
                        stop_fetching = True
                        break
                    
                    new_activities.append(activity)
                    print(f"Found new activity: {activity['start_date']}")

                if stop_fetching:
                    break
                
                params["page"] += 1
            else:
                raise Exception(f"Failed to retrieve activities: {response.status_code} {response.text}")

        if new_activities:
            # Normalize JSON to flat table
            df = pd.json_normalize(new_activities)
            
            # Ensure consistent columns if needed, or just let pandas handle it.
            # If we want to match the previous specific list of fields, we can filter, 
            # but usually keeping all data is better unless specified otherwise.
            # For now, I will keep all columns to be safe and flexible.
            
            # Append to CSV
            file_exists = os.path.isfile(CSV_FILE)
            mode = 'a' if file_exists else 'w'
            header = not file_exists
            
            df.to_csv(CSV_FILE, mode=mode, header=header, index=False)
            
            # Update metadata
            # The new last_activity_date should be the date of the *most recent* activity found.
            # Since we fetch newest first, it's the first item in new_activities.
            latest_date = new_activities[0]["start_date"]
            total_record_count += len(new_activities)
            
            save_metadata(total_record_count, latest_date)
            print(f"Saved {len(new_activities)} new activities. Total records: {total_record_count}")
        else:
            print("No new activities found.")

    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    stats = get_athlete_stats()

    if stats:
        print("Athlete Stats:")
        print(stats)
    else:
        print("Failed to retrieve stats.")
    
    refresh_data = input("Do you want to refresh the data? (y/n) \n")
    
    if refresh_data.strip().lower() == 'y':
        fetch_new_activities()
    else:
        print("No updates requested.")