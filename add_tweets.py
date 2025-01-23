from db_access import DBAccess
from datetime import timedelta
import re
import pandas as pd
import os

db = DBAccess()

# This method will add all users from the excel to our DB.
def save_tweeters_from_excel(input_file):
    # Read input Excel file
    df = pd.read_excel(input_file)
        
    # Iterate over rows
    for index, row in df.iterrows():
        user_name = row['username']
        add_tweeter_to_db(user_name)


# Add a new tweeter to the db, username is a string name of the tweeter.
def add_tweeter_to_db(tweeter_name):
   db.insert_tweeter(tweeter_name)
   print(f"A new tweeter has been added: '{tweeter_name}'")

# Add a new tweet to the db.
# tweet_id is a string id of the tweet.
# tweeter is the string name of the tweet writer.
# content is a string content, it will pass a cleanup later.
# def insert_tweet(self, tweet_id, tweeter, content):
def add_tweet_to_db(tweet_id, tweeter, content):
   db.insert_tweet(tweet_id, tweeter, content)


# This method will add all tweets from an excel file to the DB.
def save_tweets_from_excel(input_file):
    # Read input Excel file
    df = pd.read_excel(input_file)
        
    # Iterate over rows
    for index, row in df.iterrows():
        tweeter = row['tweeter']
        tweet_id = row['tweet_id']
        content = row['content']
        add_tweet_to_db(tweet_id, tweeter, content)

def preprocess_tweet(text: str) -> str:
    # Remove URLs
    text = re.sub(r"http\S+", "", text)

    # Remove mentions
    text = re.sub(r"@\S+", "", text)

    # Remove # from hashtags
    text = re.sub(r"#", "", text)

    # Remove emojis
    text = re.sub(r"[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F700-\U0001F77F\U0001F780-\U0001F7FF\U0001F800-\U0001F8FF\U0001F900-\U0001F9FF\U0001FA00-\U0001FA6F\U0001FA70-\U0001FAFF\U00002702-\U000027B0\U000024C2-\U0001F251\U0001F910-\U0001F918\U0001F980-\U0001F984\U0001F9C0]", "", text)


    # Only keep English and Arabic letters, numbers and symbols
    text = re.sub(r"[^a-zA-Z\u0600-\u06FF0-9\s,.?!'/\"]", "", text)

    # Remove extra spaces
    text = re.sub(r"\s+", " ", text)

    # Remove leading and trailing spaces
    text = text.strip()

    if len(text.split()) < 6:
        return ""

    return text

# This method will return a wanted number of tweets per user, from an excel file.
# IMPORTANT: this method will delete the selected tweets from the given file!
def get_tweets_by_tweeter(input_file, num_of_tweets):
    # Read the input Excel file
    df = pd.read_excel(input_file)
    df['tweet_id'] = df['tweet_id'].astype(str)
    df['content'] = df['content'].astype(str)
    # Group tweets by tweeter
    grouped = df.groupby('tweeter')

    # Create an empty list to store the selected tweets
    selected_tweets = []
    remaining_tweets = []

    # Select the first 10 tweets for each tweeter
    for _, group_df in grouped:
        selected_tweets.append(group_df.head(num_of_tweets))
        remaining_tweets.append(group_df.iloc[num_of_tweets:])
    
    # Create a DataFrame from the list.
    selected_tweets_df = pd.concat(selected_tweets)
    remaining_tweets_df = pd.concat(remaining_tweets)
    remaining_tweets_df.to_excel(input_file, index=False)

    return selected_tweets_df

# This method will go over a directory with xlsx files and return a new xlsx file with all wanted tweets.
def init_final_batch_excel(input_directory, num_per_user,output_file):
    # Create an empty list to store the selected tweets
    all_selected_tweets = []
    # all_selected_tweets = pd.DataFrame(columns=['tweet_id', 'tweeter', 'content'])

    # Process each input file
    for filename in os.listdir(input_directory):
        if filename.endswith('.xlsx'):
            input_file = os.path.join(input_directory, filename)
            selected_tweets = get_tweets_by_tweeter(input_file, num_per_user)
            all_selected_tweets.append(selected_tweets)
    
    # Create a DataFrame from the list.
    all_selected_tweets_df = pd.concat(all_selected_tweets)

    # Save all selected tweets to a single Excel file
    # output_file = 'initial-db-tweets/batch18_tweets_done.xlsx'
    all_selected_tweets_df.to_excel(output_file, index=False)

    print("Selected tweets from all files saved to", output_file)

def create_finished_classifications_excel(output_file):
    classifications_data = db.get_finished_classifications()
    # Create a DataFrame from the list
    classifications_df = pd.DataFrame(classifications_data)
    # Save the DataFrame to an Excel file
    classifications_df.to_excel(output_file, index=False)


# Those lines create one excel from several, taking only a number of tweets per user,
# change num to wanted number and name of output file.
# input_directory = 'batches_to_take_from'
# num_per_user = 20
# output_file = 'ready_to_load/NAME.xlsx'
# init_final_batch_excel(input_directory, num_per_user,output_file)

# Those lines insert tweets from excel to the db.
# input_file = 'ready_to_load/batch1to6ready.xlsx'
# save_tweets_from_excel(input_file)

# Those lines are in charge of creating an excel of classified data.
# output_file = 'get_finished/Positive_classifications.xlsx'
# create_finished_classifications_excel(output_file)