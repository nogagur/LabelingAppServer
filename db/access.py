import random
import re
from datetime import datetime, timedelta
from secrets import token_urlsafe
from sqlalchemy import Engine, update, func, desc
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from credentials import *
from db.models import *

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

    def add_user(self, email, password):
        """
        Adds a new user to the database.
        """
        with Session(self.engine) as session:
            user = User(
                email=email,
                password=password,
                num_classified=0,
                num_left=0
            )
            session.add(user)
            session.commit()
            return user

    def add_pro_user(self, user_id):
        """
        Adds a user to the ProUsers table, making them a pro user.
        """
        with Session(self.engine) as session:
            # Ensure the user exists
            user = session.query(User).filter(User.id == user_id).one_or_none()
            if not user:
                raise ValueError(f"User with ID {user_id} does not exist.")

            # Add the user to the ProUsers table
            pro_user = ProUser(id=user_id)
            session.add(pro_user)
            session.commit()
            return pro_user

    def get_user_by_email(self, email):
        """
        Retrieves a user by their email.
        """
        with Session(self.engine) as session:
            return session.query(User).filter(User.email == email).one_or_none()

    def validate_user(self, email, password):
        """
        Validates a user's email and password.
        Returns the user object if valid, otherwise None.
        """
        with Session(self.engine):
            # Retrieve the user by email
            user = self.get_user_by_email(email)

            # Check if the user exists and the passwords match
            if user and user.password == password:
                return user
            return None

    def get_video_by_id(self, video_id):
        """
        Retrieves a video from the database by its ID.
        Returns the video object if found, otherwise None.
        """
        with Session(self.engine) as session:
            return session.query(VideoMeta).filter(VideoMeta.id == video_id).one_or_none()

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



    def get_unclassified_video(self, user_id):
        """
        Assign an unclassified video to a user.
        Each video should be classified by 2 different users.
        """
        with Session(self.engine) as session:
            # Get videos classified by the current user
            classified_by_user = session.query(VideoClassification.video_id).filter(
                VideoClassification.classified_by == user_id
            ).subquery()

            # Get videos classified once but by another user
            classified_once = session.query(VideoMeta).join(
                VideoClassification, VideoMeta.id == VideoClassification.video_id
            ).group_by(VideoMeta.id).having(func.count(VideoClassification.video_id) == 1).filter(
                ~VideoMeta.id.in_(classified_by_user)
            ).all()

            # Get videos never classified
            never_classified = session.query(VideoMeta).filter(
                ~VideoMeta.id.in_(session.query(VideoClassification.video_id))
            ).all()

            # Choose randomly from never classified or classified once
            if classified_once and never_classified:
                if random.random() < 0.5:
                    result = classified_once
                else:
                    result = never_classified
            else:
                result = classified_once or never_classified

            # If there are available videos, pick one at random
            if result:
                random_video = random.choice(result)
                return random_video

            return None  # No available videos

    def classify_video(self, video_id, user_id, classification, features):
        """
        Stores the user's classification of a video and saves selected features.
        """
        with Session(self.engine) as session:
            # Ensure the video exists
            video = session.query(VideoMeta).filter(VideoMeta.id == video_id).one_or_none()
            if not video:
                raise ValueError(f"Video {video_id} does not exist.")

            # Ensure the user hasn't already classified this video
            existing_entry = session.query(VideoClassification).filter(
                VideoClassification.video_id == video_id,
                VideoClassification.classified_by == user_id
            ).one_or_none()
            if existing_entry:
                raise ValueError("User has already classified this video.")

            # Store classification
            classification_entry = VideoClassification(
                video_id=video_id,
                classified_by=user_id,
                classification=classification
            )
            session.add(classification_entry)
            session.commit()  # Commit classification first to get its ID

            # Retrieve classification ID
            classification_id = classification_entry.id

            # Detect if a pro user needs to classify this video
            self.check_if_pro_needed(session, video_id)

            self.add_classification_features(classification_id, features, session)

            return classification_entry

    def pro_classify_video(self, video_id, pro_user_id, classification):
        """
        Allows a pro user to classify a video that was flagged for review.
        If the pro classifies it as 'uncertain', it remains that way.
        Otherwise, the classification is finalized.
        """
        with Session(self.engine) as session:
            # Ensure the pro classification exists
            pro_entry = session.query(VideoClassification).filter(
                VideoClassification.video_id == video_id,
                VideoClassification.classified_by == pro_user_id,
                VideoClassification.classification == "unknown"
            ).one_or_none()

            if not pro_entry:
                raise ValueError("No pending pro classification found for this video.")

            # Update the classification
            pro_entry.classification = classification
            session.commit()

    def add_classification_features(self, classification_id, features, session):
        """
        Adds the features selected in the classification to the VideosClassification_Features table.
        """
        for feature_title in features:
            # Ensure the feature exists in the Features table
            feature_obj = session.query(Feature).filter(Feature.title == feature_title).one_or_none()
            if not feature_obj:
                raise ValueError(f"Feature '{feature_title}' does not exist.")

            # Insert into VideosClassification_Features
            feature_entry = VideosClassificationFeature(
                classification_id=classification_id,
                feature_id=feature_obj.id
            )
            session.add(feature_entry)
        session.commit()

    def check_if_pro_needed(self, session, video_id):
        """
        Checks if a video requires a pro classification and assigns it if necessary.
        Conditions:
        - Two users have classified it differently.
        - Any user classified it as 'uncertain'.
        """
        # Get all classifications for this video
        classifications = session.query(VideoClassification.classification).filter(
            VideoClassification.video_id == video_id
        ).distinct().all()

        # Flatten classification results
        classifications = [c[0] for c in classifications]

        # If there are two different classifications OR 'uncertain' is present
        if len(classifications) > 1 or "uncertain" in classifications:
            # Check if a pro classification already exists
            pro_entry = session.query(VideoClassification).filter(
                VideoClassification.video_id == video_id,
                VideoClassification.classification == "unknown"  # Placeholder for pro
            ).one_or_none()

            if not pro_entry:
                # todo: maybe change it to get specific pro users
                # Get all pro user IDs
                pro_users = session.query(ProUser.id).order_by(ProUser.id).all()
                pro_users = [p[0] for p in pro_users]  # Convert to list of IDs

                if not pro_users:
                    print("No pro users available.")
                    return

                next_pro_user = self.next_pro_to_assign(pro_users, session)

                # Insert new classification for the pro user with 'unknown' status
                pro_classification = VideoClassification(
                    video_id=video_id,
                    classified_by=next_pro_user,  # Assign the next pro user
                    classification="unknown"  # Placeholder until pro classifies
                )
                session.add(pro_classification)
                session.commit()
                print(f"Assigned video {video_id} to pro user {next_pro_user} for review.")

    def next_pro_to_assign(self, pro_users, session):
        # todo: change if its just a list of two
        # Find the last assigned pro user
        last_pro_entry = session.query(VideoClassification.classified_by).filter(
            VideoClassification.classified_by.in_(pro_users)
        ).order_by(desc(VideoClassification.id)).first()
        # Determine next pro user using round-robin
        if last_pro_entry:
            last_pro_user = last_pro_entry[0]
            last_pro_index = pro_users.index(last_pro_user) if last_pro_user in pro_users else -1
            next_pro_user = pro_users[(last_pro_index + 1) % len(pro_users)]
        else:
            next_pro_user = pro_users[0]  # Start with the first pro user
        return next_pro_user


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

    # # This method return the number of days left until the account is blocked.
    # def get_time_left(self, classifier):
    #     with Session(self.engine) as session:
    #         current_date = datetime.now().date()
    #         user_until = session.query(User).filter(User.key == classifier).first()
    #         if user_until is not None and user_until.valid_until is not None:
    #             valid_until_date = user_until.valid_until
    #             days_left = (valid_until_date - current_date).days
    #             return days_left if days_left >= 0 else 0
    #         else:
    #             return 0

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
            return session.query(User).filter(User.activated == True).all()
    
    
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

