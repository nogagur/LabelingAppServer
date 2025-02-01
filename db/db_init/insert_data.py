import glob
import json
import os
import re
from dotenv import load_dotenv

import psycopg2

# Load environment variables from .env file
load_dotenv()

DB_CONFIG = {
    "host": os.getenv("DB_HOST"),
    "database": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
}

def insert_tiktok_data(data, pre_class):
    """
    Inserts TikTok data into the PostgreSQL database.
    """

    try:
        # Connect to the database
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()

        # Insert each TikTok user into the TiktokUsers table
        for record in data:
            if "note" in record and (record["note"] == 'Profile is private' or record['note'] == 'No videos found to match the date filter'):
                continue

            insert_user(cur, record, pre_class)
            insert_video(cur, record)
            print("Finished inserting data for video:", record["id"])

        # Commit changes and close the connection
        conn.commit()
        cur.close()
        conn.close()
        print("Data inserted successfully!")

    except Exception as e:
        print("Error inserting data:", e)

def insert_hashtags(cur, hashtags):
    hashtag_ids = []
    for hashtag in hashtags:
        cur.execute("""
                    INSERT INTO Hashtags (content)
                    VALUES (%s)
                    ON CONFLICT (content) DO NOTHING
                    RETURNING id
                """, (hashtag["name"],))
        result = cur.fetchone()
        if result:
            hashtag_ids.append(result[0])
        else:
            cur.execute("SELECT id FROM Hashtags WHERE name = %s", (hashtag,))
            hashtag_ids.append(cur.fetchone()[0])
    return hashtag_ids

def insert_data(cur, table, data):
    # Prepare the columns and values for the INSERT statement
    columns = list(data.keys())
    values = list(data.values())

    # Filter out None values to let the database use default values
    filtered_columns = [col for col, val in zip(columns, values) if val is not None]
    filtered_values = [val for val in values if val is not None]

    # Check if filtered data is empty after filtering None values
    if not filtered_columns or not filtered_values:
        return  # Nothing to insert

    # Construct the SQL query dynamically
    query = f"""
        INSERT INTO {table} ({', '.join(filtered_columns)})
        VALUES ({', '.join(['%s'] * len(filtered_values))})
        ON CONFLICT (id) DO NOTHING
    """

    # Execute the query
    cur.execute(query, filtered_values)

def insert_user(cur, user, pre_classification):
    user_data = {
        "id": user["authorMeta"]["id"],
        "username": user["authorMeta"]["name"],
        "nickname": user["authorMeta"]["nickName"],
        "description": user["authorMeta"]["signature"],
        "region": user["authorMeta"]["region"],
        "video_num": user["authorMeta"]["video"],
        "fans": user["authorMeta"]["fans"],
        "following": user["authorMeta"]["following"],
        "friends": user["authorMeta"]["friends"],
        "likes": user["authorMeta"]["heart"],
        "thumbnail": user["authorMeta"]["avatar"],
        "pre_classification": pre_classification
    }
    insert_data(cur, "TiktokUsers", user_data)

def insert_hashtags(cur, hashtags):
    hashtag_ids = []
    for hashtag in hashtags:
        query = """
            INSERT INTO Hashtags (content)
            VALUES (%s)
            ON CONFLICT (content) DO NOTHING
            RETURNING id
        """
        cur.execute(query, (hashtag["name"],))
        result = cur.fetchone()  # Fetch the returned ID, if any
        if result:
            hashtag_ids.append(result[0])  # New ID returned from the INSERT
        else:
            # If no ID was returned, it means the hashtag already exists, so fetch its ID
            cur.execute("SELECT id FROM Hashtags WHERE content = %s", (hashtag["name"],))
            hashtag_ids.append(cur.fetchone()[0])
    return hashtag_ids


def insert_music(cur, music):
    music_data = {
        "id": music.get("musicId"),
        "name": music.get("musicName"),
        "author": music.get("musicAuthor"),
        "play_link": music.get("playUrl")
    }
    insert_data(cur, "Music", music_data)

def insert_video(cur, data):
    # Insert music data first
    insert_music(cur, data.get("musicMeta", {}))

    # Insert hashtags and get their IDs
    hashtag_ids = insert_hashtags(cur, data.get("hashtags", []))

    # Prepare video data
    video_data = {
        "id": data.get("id"),
        "description": data.get("text"),
        "user_id": data.get("authorMeta", {}).get("id"),
        "play_count": data.get("playCount"),
        "share_count": data.get("shareCount"),
        "comment_count": data.get("commentCount"),
        "created_at": data.get("createTimeISO"),
        "duration": data.get("videoMeta", {}).get("duration"),
        "height": data.get("videoMeta", {}).get("height"),
        "width": data.get("videoMeta", {}).get("width"),
        "video_file": data.get("videoMeta", {}).get("downloadAddr"),
        "video_thumbnail": data.get("videoMeta", {}).get("coverUrl"),
        "web_url": data.get("webVideoUrl"),
        "music_id": data.get("musicMeta", {}).get("musicId")
    }

    # Check if "video_file" exists before inserting
    if not video_data["video_file"]:
        print(f"Skipping video {video_data['id']} due to missing video file.")
        return

    insert_data(cur, "VideosMeta", video_data)

    # Insert records into VideosMeta_Hashtags table
    for hashtag_id in hashtag_ids:
        query = """
                INSERT INTO VideosMeta_Hashtags (video_id, hashtag_id)
                VALUES (%s, %s)
                ON CONFLICT DO NOTHING
            """
        cur.execute(query, (video_data["id"], hashtag_id))

def load_tiktok_json(file_path):
    """
    Loads TikTok data from a JSON file.
    """
    with open(file_path, "r") as f:
        return json.load(f)

def extract_group(filename):
    match = re.search(r'dataset_(hamas|fatah|none)', filename)
    if match:
        return match.group(1)  # Return the group name directly
    return 'unknown'

if __name__ == "__main__":
    # Directory containing TikTok JSON files
    tiktok_json_directory = "../tiktok_data/"

    # Iterate through all JSON files in the directory
    for file_path in glob.glob(os.path.join(tiktok_json_directory, "*.json")):
        print(f"Processing file: {file_path}")

        try:
            # Extract pre_classification from the file name
            pre_classification = extract_group(file_path)

            # Load the JSON data from the file
            tiktok_data = load_tiktok_json(file_path)

            # Insert data into the database
            insert_tiktok_data(tiktok_data, pre_classification)

        except Exception as e:
            print(f"Error processing file {file_path}: {e}")