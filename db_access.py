import random
import re
from datetime import datetime, timedelta
from secrets import token_urlsafe
from sqlalchemy import Engine, update, func
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.orm import declarative_base

from credentials import *
from models import Passcode, Tweet, Classification, Tweeter, ProBank ,Base


class Singleton(type):
    def __init__(cls, name, bases, dict):
        super().__init__(name, bases, dict)
        cls.instance = None

    def __call__(cls, *args, **kw):
        if cls.instance is None:
            cls.instance = super().__call__(*args, **kw)
        return cls.instance


class DBAccess(metaclass=Singleton):
    def __init__(self):
        self.engine: Engine = create_engine(DB)

    # A method that is generating a passcode for a user.
    def create_passcode(self, email, num_days):
        with Session(self.engine) as session:
            passcode = generate_passcode(num_days)
            session.add(
                Passcode(key=passcode.key, valid_until=passcode.valid_until, created=passcode.created, email=email))
            session.commit()
        return passcode.key

    # A method that returns a passcode object.
    def get_passcode(self, key):
        with Session(self.engine) as session:
            result = session.query(Passcode).filter(Passcode.key == key)
            return result.one_or_none()

    # A method that is used to activate the emails of the new users.
    def activate_passcode_by_email(self, email):
        with Session(self.engine) as session:
            session.execute(update(Passcode).where(Passcode.email == email).values(activated=True))
            session.commit()

    # This method is in charge of returning a tweet object.
    def get_tweet(self, tweet_id):
        with Session(self.engine) as session:
            return session.query(Tweet).filter(Tweet.id == tweet_id).one_or_none()

    # This method is in charge of adding a new tweet to the db.
    def insert_tweet(self, tweet_id, tweeter, content):
        with Session(self.engine) as session:
            # Do a cleanup of the content.
            content = preprocess_tweet(content)
            if not content:
                return
            session.add(Tweet(id=tweet_id, tweeter=tweeter, content=content))
            session.commit()

    # This method inserts a new tweeter to the db.
    def insert_tweeter(self, username):
        with Session(self.engine) as session:
            session.add(Tweeter(username=username))
            session.commit()

    def insert_to_probank(self, tweet_id):
        with Session(self.engine) as session:
            session.add(ProBank(tweet=tweet_id, done=False))
            session.commit()

    # This method returns the tweeter as an object.
    def get_tweeter(self, username):
        with Session(self.engine) as session:
            return session.query(Tweeter).filter(Tweeter.username == username).one_or_none()

    # This method refactors the tweet, in case of a contradiction and a pro's oppinion, or if
    # a new tweet is added to the classification table and is now assigned to the user.
    def __reserve_tweet(self, tweet, passcode):
        with Session(self.engine) as s:
            # Check if the tweet is already assigned to the same user.
            if s.query(Classification).filter(Classification.tweet == tweet.id).filter(
                    Classification.classifier == passcode).first():
                return
            # Otherwise, assign the tweet to the user.
            classification = Classification(tweet=tweet.id,
                                            classifier=passcode,
                                            classification="N/A",
                                            classified_at=datetime.now())
            s.add(classification)
            s.commit()

    # This method is in charge of assigning the tweet to a pro and updating the pro bank.
    def __reserve_tweet_pro(self, tweet, passcode, pro_tweet):
        with Session(self.engine) as s:
            # Update the pro table that a pro user got a new classification.
            s.execute(update(ProBank).where(ProBank.tweet == pro_tweet.tweet).values(done=True))
            s.commit()

            # Check if the tweet is already assigned to the same user.
            if s.query(Classification).filter(Classification.tweet == tweet.id).filter(
                    Classification.classifier == passcode).first():
                return
            

            classification = Classification(tweet=tweet.id,
                                            classifier=passcode,
                                            classification="N/A",
                                            classified_at=datetime.now())
            s.add(classification)
            s.commit()
        
        
    # Update the starting classifying time for the current tweet. 
    def update_start(self, tweet, passcode):
        with Session(self.engine) as session:
            session.execute(
                update(Classification)
                .where((Classification.tweet == tweet.id) & (Classification.classifier == passcode))
                .values(started_classification=datetime.now())
            )
            session.commit()

    def get_different_unclassified_tweet(self, passcode, curr_id):
        with Session(self.engine) as session:
            # Check if there is a ongoing classification, the status is N/A
            result = session.query(Tweet).filter(Tweet.id == Classification.tweet).filter(
                Classification.classifier == passcode).filter(
                Classification.classification == "N/A").filter(
                Classification.tweet != curr_id).first()
            if result:
                return result
            else:
                return None
                
    def get_different_unclassified_tweet_pro(self, passcode):
        with Session(self.engine) as session:
            # Check if there are tweets in the pro bank that are not assigned already.
            pro_tweet = session.query(ProBank).filter(ProBank.done == False).first()
            
            # If there are tweets for a pro, choose a random one and assign it to the user.
            if pro_tweet:
                tweet = session.query(Tweet).filter(Tweet.id == pro_tweet.tweet).first()
                self.__reserve_tweet_pro(tweet, passcode,pro_tweet)
                return tweet

            else:
                return None

    # This method is in charge of assigning a tweet to the user.
    def get_unclassified_tweet(self, passcode):
        with Session(self.engine) as session:
            # Check if there is a ongoing classification, the status is N/A
            result = session.query(Tweet).filter(Tweet.id == Classification.tweet).filter(
                Classification.classifier == passcode).filter(
                Classification.classification == "N/A").first()
            if result:
                return result

            # Check if the current user is a pro. If so, assign tweets accordingly.
            if self.get_passcode(passcode).professional:
                # Check if there are tweets in the pro bank that are not assigned already.
                pro_tweet = session.query(ProBank).filter(ProBank.done == False).first()
                
                # If there are tweets for a pro, choose a random one and assign it to the user.
                if pro_tweet:
                    tweet = session.query(Tweet).filter(Tweet.id == pro_tweet.tweet).first()
                    self.__reserve_tweet_pro(tweet, passcode,pro_tweet)
                    return tweet

                else:
                    return None

            # Get list of tweets that were classified exactly once by any classifier except this one that are not N/A
            classified_by_curr = session.query(Classification.tweet).filter(Classification.classifier == passcode).group_by(Classification.tweet).all()
            
            tweet_ids_to_exclude = [row[0] for row in classified_by_curr if row[0] is not None]

            classified_once = session.query(Tweet)\
                .filter(Tweet.id == Classification.tweet)\
                .group_by(Tweet.id)\
                .having(func.count(Classification.tweet) == 1)\
                .filter(Classification.classifier != passcode).filter(Tweet.id.notin_(tweet_ids_to_exclude)).all()

            # Return all tweets that are not classified yet.
            never_classified = session.query(Tweet).filter(~Tweet.id.in_(session.query(Classification.tweet))).all()

            # Randomly choose a tweet that is not classified yet or needs to be classified secondly.
            if classified_once and never_classified:
                if random.random() < 0.5:
                    result = classified_once
                else:
                    result = never_classified
            else:
                result = classified_once or never_classified

            ids = [tweet.id for tweet in result]
            if ids:
                random_id = random.choice(ids)
                tweet = next(tweet for tweet in result if tweet.id == random_id)
                if tweet:
                    if session.query(Classification).filter(Classification.tweet == tweet.id).filter(
                    Classification.classifier == passcode).first():
                        return
                    self.__reserve_tweet(tweet, passcode)
                    return tweet

            # The next lines in charge of mass assign (100) of tweets to users, use when lines
            # 183-191 and 138-142, 146-157 are commented.

            # if ids:
            #     random.shuffle(ids)
            #     selected_ids = set(ids[:8])
            #     for random_id in selected_ids:
            #         tweet = next((tweet for tweet in result if tweet.id == random_id), None)
            #         if tweet:
            #             if session.query(Classification).filter(Classification.tweet == tweet.id).filter(
            #                 Classification.classifier == passcode).first():
            #                 continue
            #             self.__reserve_tweet(tweet, passcode)

    # This method is in charge of the whole classification, without the professionals.
    def classify_tweet(self, tweet_id, passcode, classification, features):
        with Session(self.engine) as session:
            # The classification is made by a pro user.
            if self.get_passcode(passcode).professional:
                return self.classify_tweet_pro(tweet_id, passcode, classification, features)

            # Search for the wanted tweet and making sure it is unclassified.
            result = session.query(Classification).filter(Classification.tweet == tweet_id).filter(
                Classification.classifier == passcode).filter(
                Classification.classification == "N/A").one_or_none()
            if not result:
                return False
            # Check if this classification needs a pro's attention.
            self.is_pro_needed(tweet_id,classification,passcode)
            
            # Submiting the classification.
            session.execute(update(Classification).where(Classification.tweet == tweet_id).where(
                Classification.classifier == passcode).values(classification=classification, features=features,
                                                                classified_at=datetime.now()))
            session.commit()
            return True
        
    # The classification is made by a pro user.
    def classify_tweet_pro(self, tweet_id, passcode, classification, features):
        with Session(self.engine) as session:
            # Search for the wanted tweet and making sure it is unclassified.
            result = session.query(Classification).filter(Classification.tweet == tweet_id).filter(
                Classification.classifier == passcode).filter(
                Classification.classification == "N/A").one_or_none()
            if not result:
                return False
            
            # Get all the instances of the same tweet and make sure all are classified with the same value.
            tweets_to_update = session.query(Classification).filter(Classification.tweet == tweet_id).filter(
                Classification.classifier != passcode).all()

            # Update user's classifications to pro's decision, without time update.
            for tweet in tweets_to_update:
                session.execute(update(Classification).where(Classification.tweet == tweet_id).where(
                    Classification.classifier == tweet.classifier).values(classification=classification, features=features))
                session.commit()

            # Update the pro's classification with time update.
            session.execute(update(Classification).where(Classification.tweet == tweet_id).where(
                Classification.classifier == passcode).values(classification=classification, features=features,
                                                                classified_at=datetime.now()))
            session.commit()
            return True

    # This method is in charge of checking if the new classification needs a pro's attention.
    # If this is the fist instance of the tweet in the classifications table, then no need in a pro.
    # Otherwise, if this is the second instance, it is being tested for contradiction.
    def is_pro_needed(self, tweet_id, classification,classifier):
        is_needed = False
        with Session(self.engine) as session:
            # Check if there is another instance of this tweet.
            curr_tweet_classifications = session.query(Classification).filter(Classification.tweet == tweet_id).filter(
                Classification.classification != "N/A").filter(Classification.classifier != classifier).all()
            print(curr_tweet_classifications)
            if len(curr_tweet_classifications) > 0:
                # If the classification is "unknown", then a pro is needed.
                if classification == "Unknown":
                    print("Classification is unknown.")
                    is_needed = True
                # Check if both classifications are similar.
                for curr_class in curr_tweet_classifications:
                    if curr_class.classification != classification:
                        print(f"this classification: {classification}, found classificaion: {curr_class.classification}")
                        is_needed = True

            # Pro's assistance is needed.
            if is_needed:
                print("Classification needs pro.")
                # Check if the tweet is already in the pro bank.
                if not session.query(ProBank).filter(ProBank.tweet == tweet_id).first():
                    print("Adding classification to pro bank.")
                    self.insert_to_probank(tweet_id)

    # This method returns the passcode of a desired email.
    def get_passcode_by_email(self, email):
        with Session(self.engine) as session:
            return session.query(Passcode).filter(Passcode.email == email).one_or_none()

    # This method return the number of tweets classified as positive, by a user.
    def get_num_positive_classifications(self, classifier):
        with Session(self.engine) as session:
            return session.query(Classification).filter(Classification.classifier == classifier).filter(
                Classification.classification == "Positive").count()

    
     # This method return the number of tweets classified as irrelevant, by a user.
    def get_num_irrelevant_classifications(self, classifier):
        with Session(self.engine) as session:
            return session.query(Classification).filter(Classification.classifier == classifier).filter(
                Classification.classification == "Irrelevant").count()
        
    # This method return the number of tweets classified as negative, by a user.
    def get_num_negative_classifications(self, classifier):
        with Session(self.engine) as session:
            return session.query(Classification).filter(Classification.classifier == classifier).filter(
                Classification.classification == "Negative").count()
        
    # This method return the number of tweets unclassified, by a user.
    def get_num_remaining_classifications(self, classifier):
        with Session(self.engine) as session:
            return session.query(Classification).filter(Classification.classifier == classifier).filter(
                Classification.classification == "N/A").count()
        
    # This method identifies tweet ids that occur three or more times within the classification table
    def find_duplicate_tweet_ids(self):
        with Session(self.engine) as session:
            # Query to count occurrences of each tweet ID
            tweet_id_counts = session.query(Classification.tweet, func.count(Classification.tweet)).group_by(Classification.tweet).all()
            # Filter out tweet IDs with counts greater than 1
            duplicate_tweet_ids = [tweet_id for tweet_id, count in tweet_id_counts if count > 2]    
            return duplicate_tweet_ids

    # This method return the average time it takes a user to classify a tweet.
    def get_average_classification_time(self, classifier):
        with Session(self.engine) as session:
            all_seconds = 0
            all_classifications = session.query(Classification).filter(Classification.classifier == classifier).filter(
                Classification.classification != "N/A").all()
            num_of_classifications = len(all_classifications)
            if num_of_classifications > 0:
                for curr_classification in all_classifications:
                    start_time = curr_classification.started_classification
                    end_time = curr_classification.classified_at
                    time_taken = (end_time - start_time).total_seconds()
                    all_seconds += time_taken
                return all_seconds / num_of_classifications

            else:
                return 0

    # This method return the number of days left until the account is blocked.
    def get_time_left(self, classifier):
        with Session(self.engine) as session:
            current_date = datetime.now().date()
            user_until = session.query(Passcode).filter(Passcode.key == classifier).first()
            if user_until is not None and user_until.valid_until is not None:
                valid_until_date = user_until.valid_until
                days_left = (valid_until_date - current_date).days
                return days_left if days_left >= 0 else 0
            else:
                return 0

    # This method returns the number of tweets classified by a user.
    def get_num_classifications(self, classifier):
        with Session(self.engine) as session:
            return session.query(Classification).filter(Classification.classifier == classifier).filter(
                Classification.classification != "N/A").count()


    # This method is in charge of a major content cleanup in the db.
    def preprocess_all_tweets(self):
        with Session(self.engine) as session:
            tweets = session.query(Tweet).all()
            for tweet in tweets:
                tweet.content = preprocess_tweet(tweet.content)
                if tweet.content == "":
                    session.delete(tweet)
            session.commit()

    # This method returns the number of tweets a specific tweeter has in the db.
    def count_tweets_by_tweeter(self, tweeter):
        with Session(self.engine) as session:
            return session.query(Tweet).filter(Tweet.tweeter == tweeter).count()

    # This method will check how many irrelevant tweets a specific tweeter has.
    def count_irrelevant_tweets_by_tweeter(self, tweeter):
        with Session(self.engine) as session:
            return session.query(Classification).filter(Classification.tweet == Tweet.id).filter(
                Tweet.tweeter == tweeter).filter(Classification.classification == "Irrelevant").count()
        
    # This method will check how many irrelevant tweets a specific tweeter has.
    def get_users(self):
        with Session(self.engine) as session:
            return session.query(Passcode).filter(Passcode.activated == True).all()
    
    
    def get_total_classifications(self):
        with Session(self.engine) as session:
            return session.query(func.count(func.distinct(Classification.tweet))) \
                                    .filter(Classification.classification != "N/A") \
                                    .scalar()
    
    
    def get_total_negative_classifications(self):
        with Session(self.engine) as session:
            return session.query(func.count(func.distinct(Classification.tweet))) \
                                    .filter(Classification.classification == "Negative") \
                                    .scalar()

    def get_total_positive_classifications(self):
        with Session(self.engine) as session:
            return session.query(func.count(func.distinct(Classification.tweet))) \
                                    .filter(Classification.classification == "Positive") \
                                    .scalar()

    def get_total_irrelevant_classifications(self):
        with Session(self.engine) as session:
            return session.query(func.count(func.distinct(Classification.tweet))) \
                                    .filter(Classification.classification == "Irrelevant") \
                                    .scalar()
    
    def get_finished_classifications(self):
        # Create a list to store classification data
        classifications_data = []

        with Session(self.engine) as session:
            # Query to get unique tweet IDs with desired classifications
            negative_classifications = session.query(
                Classification.id,
                Classification.tweet,
                Classification.classification,
                Classification.features,
                Tweet.content
            ).join(Tweet, Classification.tweet == Tweet.id).filter(Classification.classification == "Positive").distinct(Classification.tweet).all()

            # Append classification data to the list
            for classification in negative_classifications:

                classifications_data.append({
                    'id': classification.id,
                    'tweet_id': classification.tweet,
                    'classification': classification.classification,
                    'features': classification.features,
                    'tweet': classification.content
                })
            
            return classifications_data

        
# This method is in charge of a cleanup of the content.
def preprocess_tweet(text: str) -> str:
    # Remove URLs
    text = re.sub(r"http\S+", "", text)

    # Remove mentions
    text = re.sub(r"@\S+", "", text)

    # Remove emojis
    text = re.sub(r"[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F700-\U0001F77F\U0001F780-\U0001F7FF\U0001F800-\U0001F8FF\U0001F900-\U0001F9FF\U0001FA00-\U0001FA6F\U0001FA70-\U0001FAFF\U00002702-\U000027B0\U000024C2-\U0001F251\U0001F910-\U0001F918\U0001F980-\U0001F984\U0001F9C0]", "", text)

    # Only keep English and Arabic letters, numbers and symbols
    text = re.sub(r"[^a-zA-Z\u0600-\u06FF0-9\s,.?!'/\"#]", "", text)

    # Remove extra spaces
    text = re.sub(r"\s+", " ", text)

    # Remove leading and trailing spaces
    text = text.strip()

    if len(text.split()) < 6:
        return ""

    return text


# This method is in charge of creating a user in the db.
def generate_passcode(num_days):
    duration=timedelta(days=num_days)
    key = token_urlsafe(6)
    token = Passcode(key=key, valid_until=datetime.now() + duration, created=datetime.now())
    return token


# The next lines are in charge of bulk classification 
# db = DBAccess()
# users = [...]

# for i, user in enumerate(users, start=1):
#     db.get_unclassified_tweet(user)
#     print(f"{user} finished [{i}/{len(users)}]")

# for user in users:
#     num = db.get_num_remaining_classifications(user)
#     print(f"user: {user} has more: {num}")


# The nex lines in charge of init of the DB.
# try:
#     Base.metadata.create_all(db.engine)
#     print("Tables created successfully")
# except Exception as e:
#     print("Error occurred during table creation:", e)

