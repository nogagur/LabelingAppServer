import tweepy
import pandas as pd
from credentials import *

# Load the Excel file
file_path = 'user-ID-map-left.xlsx'
data = pd.read_excel(file_path)

# Function to extract usernames from URLs
def extract_username(url):
    if url and isinstance(url, str):
        if url.startswith("/"):
            return url.split('/')[1] 
        else:
            parts = url.split('/')
            if len(parts) >= 4 and parts[3]:
                return parts[3].split('?')[0]
    return None

data['username'] = data['חשבון '].apply(extract_username)


# Setup Tweepy API authentication
client = tweepy.Client(twitter_bearer,twitter_api,twitter_api_sec,twitter_access,twitter_access_sec)


# Function to fetch Twitter user ID
# def get_tweets(id):
#     all_tweets = client.get_users_tweets(id=id, max_results=5, tweet_fields=['text'])
#     all_tweets_data = all_tweets.data
#     for tweet in all_tweets_data:
#         print(f"tweet_id: {tweet.id}, text: {tweet.text}")

def fetch_twitter_id(username):
    try:
        user = client.get_user(username=username)
        return str(user.data.id)
    except Exception as e:
        return f"Error: {str(e)}"

# Fetch Twitter IDs
data['twitter_id'] = data['username'].apply(fetch_twitter_id)

# Save the updated DataFrame back to Excel
output_path = 'left_users.xlsx'
data.to_excel(output_path, index=False)

print("Updated Excel file has been saved to:", output_path)
