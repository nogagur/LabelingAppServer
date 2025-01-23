import json
import re

import psycopg2

# Database connection settings
DB_CONFIG = {
    "host": "localhost",
    "database": "tiktok_project",
    "user": "noga",
    "password": "root"
}

def insert_tiktok_data(data, pre_classification):
    """
    Inserts TikTok data into the PostgreSQL database.
    """

    try:
        # Connect to the database
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()

        # Insert each TikTok user into the TiktokUsers table
        for record in data:
            if "note" in record and record["note"] == 'Profile is private':
                continue

            # insert_user(cur, record, pre_classification)
            insert_video(cur, record)
            print("Finished inserting data for video:", record["id"])

        # Commit changes and close the connection
        conn.commit()
        cur.close()
        conn.close()
        print("Data inserted successfully!")

    except Exception as e:
        print("Error inserting data:", e)


def insert_user(cur, user, pre_classification):
    cur.execute("""
                INSERT INTO TiktokUsers (
                    id, username, nickname, description, region, video_num, fans, following, friends, likes, thumbnail, pre_classification
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO NOTHING
            """, (
        user["authorMeta"]["id"], user["authorMeta"]["name"], user["authorMeta"]["nickName"],
        user["authorMeta"]["signature"],
        user["authorMeta"]["region"], user["authorMeta"]["video"], user["authorMeta"]["fans"],
        user["authorMeta"]["following"],
        user["authorMeta"]["friends"], user["authorMeta"]["heart"], user["authorMeta"]["avatar"], pre_classification
    ))

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

def insert_music(cur, music):
    cur.execute("""
                INSERT INTO Music (id, name, author, play_link)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (id) DO NOTHING
            """, (
        music["musicId"], music["musicName"], music["musicAuthor"], music['playUrl']
    ))


def insert_video(cur, data):
    # Insert music data first
    insert_music(cur, data["musicMeta"])

    # Insert hashtags and get their IDs
    hashtag_ids = insert_hashtags(cur, data["hashtags"])

    # Insert video data
    cur.execute("""
                    INSERT INTO VideosMeta (
                        id, description, user_id, play_count, share_count, comment_count, created_at, hashtags, duration, height, width, video_file, video_thumbnail, web_url, music_id
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO NOTHING
                """, (
        data["id"], data["text"], data["authorMeta"]["id"], data["playCount"], data["shareCount"],
        data["commentCount"],
        data["createTimeISO"], hashtag_ids, data["videoMeta"]["duration"], data["videoMeta"]["height"], data["videoMeta"]["width"], data["videoMeta"]["downloadAddr"],
        data["videoMeta"]["coverUrl"], data["webVideoUrl"], data["musicMeta"]["musicId"]
    ))


def load_tiktok_json(file_path):
    """
    Loads TikTok data from a JSON file.
    """
    with open(file_path, "r") as f:
        return json.load(f)

def extract_group_number(filename):
    groups = {'hamas': 1, 'fatah': 2, 'none': 3}
    match = re.search(r'dataset_(hamas|fatah|none)', filename)
    if match:
        group = match.group(1)
        return groups[group]
    return 0

if __name__ == "__main__":
    # Path to the TikTok JSON file
    tiktok_json_path = "../tiktok_data/dataset_hamas1after710_2025-01-21_08-43-34-953.json"

    # Load and insert data
    pre_classification = extract_group_number(tiktok_json_path)
    tiktok_data = load_tiktok_json(tiktok_json_path)
    # print(tiktok_data)
    insert_tiktok_data(tiktok_data, pre_classification)
