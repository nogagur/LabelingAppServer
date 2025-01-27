import tweepy
import pandas as pd

from credentials import *

client = tweepy.Client(twitter_bearer,twitter_api,twitter_api_sec,twitter_access,twitter_access_sec)

# Returns tweets of the given user id.
def get_tweets(id, username):
    all_tweets = client.get_users_tweets(id=id, max_results=100, tweet_fields=['text'], exclude=['retweets'])
    # Check if all_tweets is None or not
    if all_tweets is None:
        return [] 

    all_tweets_data = all_tweets.data
    if all_tweets_data is None:
        return []

    tweets_list = []
    
    for tweet in all_tweets_data:
        tweets_list.append({
            'tweet_id': str(tweet.id),
            'tweeter': username,
            'content': tweet.text
        })
    return tweets_list

# This method will fetch some tweets from each of the given tweeter accounts.
def fetch_and_save_tweets(input_file, output_file):
    # Read input Excel file
    df = pd.read_excel(input_file)
    
    tweets_data = []
    
    # Iterate over rows
    for index, row in df.iterrows():
        user_name = row['username']
        user_id = row['id']
        tweets = get_tweets(user_id,user_name)
        tweets_data.extend(tweets)    
    
    if tweets_data:
        tweets_df = pd.DataFrame(tweets_data)
        # Save tweets to a new Excel file
        tweets_df.to_excel(output_file, index=False)
    else:
        print("No tweets were retrieved.")

# Returns the tweet with the given id.
def get_tweet(id):
    all_tweets = client.get_tweet(id=id)
    print(all_tweets)


def add_tweets_to_db(currId):
    tweets = client.get_users_tweets(id=currId, max_results=5)
    for tweet in tweets.data:
        print(f"Tweet ID: {tweet.id}")
        print(f"Text: {tweet.text}")
        print(f"Tweeter: {id}")

# Returns the user id of the given username.
def fetch_twitter_id(username):
    try:
        user = client.get_user(username=username)
        return user.data.id  # Twitter ID as a string
    except Exception as e:
        return f"Error: {str(e)}"

# Retuns the username from the given url.
def extract_username(url):
    if url and isinstance(url, str):
        if url.startswith("/"):
            return url.split('/')[1]
        else:
            parts = url.split('/')
            if len(parts) >= 4 and parts[3]:
                return parts[3].split('?')[0]
    return None

# if __name__ == '__main__':
    # Those lines take care of fetching tweeters via the api.
    # input_file = 'user-maps/users-batch17.xlsx'
    # output_file = 'user-tweet-batches/batch17.xlsx'
    # fetch_and_save_tweets(input_file, output_file)
