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
                password=password
            )
            session.add(user)
            session.commit()
            session.refresh(user)

            return {
                "id": user.id,
                "email": user.email,
                "password": user.password
            }

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
            return {"id": pro_user.id}

    def get_user_by_email(self, email):
        """
        Retrieves a user by their email.
        """
        with Session(self.engine) as session:
            return session.query(User).filter(User.email == email).one_or_none()

    def get_user_by_id(self, user_id):
        """
        Retrieves a user by their ID.
        """
        with Session(self.engine) as session:
            return session.query(User).filter(User.id == user_id).one_or_none

    def validate_user(self, password):
        """
        Validates a user by password.
        Returns the user object if valid, otherwise None.
        """
        with Session(self.engine) as session:
            # Find the first user with this password
            user = session.query(User).filter(User.password == password).first()

            return user  # Returns None if no user is found

    # Returns all users
    def get_all_users(self):
        with Session(self.engine) as session:
            return session.query(User).all()

    def get_pro_users(self):
        with Session(self.engine) as session:
            # Fetch all pro user IDs from the ProUsers table
            pro_user_ids = session.query(ProUser.id).all()

            # Return list of ids
            return {pro_id[0] for pro_id in pro_user_ids}

    # Returns all users who aren't pro users
    def get_non_pro_users(self):
        with Session(self.engine) as session:
            pro_user_ids = session.query(ProUser.id).subquery()

            # Get users whose IDs are NOT in ProUsers
            non_pro_users = session.query(User).filter(User.id.notin_(pro_user_ids)).all()

            return non_pro_users

    def get_video_by_id(self, video_id):
        """
        Retrieves a video from the database by its ID.
        Returns the video object if found, otherwise None.
        """
        with Session(self.engine) as session:
            return session.query(VideoMeta).filter(VideoMeta.id == video_id).one_or_none()

    def get_video_for_user(self, user_id):
        """
        Assigns a new video to a user.
        Ensures each video is assigned to at most 2 users.
        Selects a video randomly from:
          - Videos that have never been assigned.
          - Videos assigned only once.
        Inserts a classification entry with 'N/A' for later updating.
        """
        with Session(self.engine) as session:
            # Find all videos that are either unassigned or assigned to only one user
            eligible_videos = session.query(VideoMeta.id).outerjoin(
                VideoClassification, VideoMeta.id == VideoClassification.video_id
            ).group_by(VideoMeta.id).having(func.count(VideoClassification.video_id) < 2).all()

            if not eligible_videos:
                print("No available videos to assign.")
                return None

            # Select a video randomly from the eligible list
            video_id = random.choice([v[0] for v in eligible_videos])

            # Check if user already has this video assigned
            existing_entry = session.query(VideoClassification).filter(
                VideoClassification.video_id == video_id,
                VideoClassification.classified_by == user_id
            ).one_or_none()

            video = session.query(VideoMeta).filter(VideoMeta.id == video_id).one()
            if existing_entry:
                return video

            # Assign the video to the user by inserting a new classification record with 'N/A'
            classification_entry = VideoClassification(
                video_id=video_id,
                classified_by=user_id,
                classification="N/A"
            )
            session.add(classification_entry)
            session.commit()

            return video

    def classify_video(self, video_id, user_id, classification, features):
        """
        Updates an existing 'N/A' classification record with the user's classification.
        Also saves selected features and checks if a pro review is needed.
        """
        with Session(self.engine) as session:
            # Ensure the video exists
            video = session.query(VideoMeta).filter(VideoMeta.id == video_id).one_or_none()
            if not video:
                raise ValueError(f"Video {video_id} does not exist.")

            # Find the user's existing classification entry for this video
            classification_entry = session.query(VideoClassification).filter(
                VideoClassification.video_id == video_id,
                VideoClassification.classified_by == user_id,
                VideoClassification.classification == "N/A"
            ).one_or_none()

            if not classification_entry:
                raise ValueError(f"User {user_id} does not have an open classification for Video {video_id}.")

            # Update classification from 'N/A' to the user's choice
            classification_entry.classification = classification

            # Save selected features in VideosClassification_Features
            self.add_classification_features(classification_entry.id, features, session)

            # Detect if a pro user is needed due to conflict or "uncertain" classification
            self.check_if_pro_needed(session, video_id)

            session.commit()
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
                VideoClassification.classification == "N/A"
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
        # Get all classifications for this video, excluding 'N/A'
        classifications = session.query(VideoClassification.classification).filter(
            VideoClassification.video_id == video_id,
            VideoClassification.classification != "N/A"
        ).distinct().all()

        # Flatten classification results
        classifications = [c[0] for c in classifications]

        # If there are two different classifications OR 'uncertain' is present
        if len(classifications) > 1 or "uncertain" in classifications:
            # Check if a pro classification already exists
            pro_entry = session.query(VideoClassification).filter(
                VideoClassification.video_id == video_id,
                VideoClassification.classification == "N/A"
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
                    classification="N/A"  # Placeholder until pro classifies
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

    def get_uploader_username(self, video_id):
        """ Returns the video's uploader username """
        with Session(self.engine) as session:
            uploader = session.query(TiktokUser.username).join(
                VideoMeta, TiktokUser.id == VideoMeta.user_id
            ).filter(VideoMeta.id == video_id).one_or_none()

            return uploader[0] if uploader else "unknown"

    # This method return the number of videos classified as hamas, by a user.
    def get_num_hamas_by_user(self, classifier):
        with Session(self.engine) as session:
            return session.query(VideoClassification).filter(VideoClassification.classified_by == classifier).filter(
                VideoClassification.classification == "Hamas").count()

    # This method return the number of videos classified as fatah, by a user.
    def get_num_fatah_by_user(self, classifier):
        with Session(self.engine) as session:
            return session.query(VideoClassification).filter(VideoClassification.classified_by == classifier).filter(
                VideoClassification.classification == "Fatah").count()

    # This method return the number of videos classified as not identified with an organization, by a user.
    def get_num_none_by_user(self, classifier):
        with Session(self.engine) as session:
            return session.query(VideoClassification).filter(VideoClassification.classified_by == classifier).filter(
                VideoClassification.classification == "None").count()

    # This method return the number of videos unclassified, by a user.
    def get_num_remaining_classifications(self, classifier):
        with Session(self.engine) as session:
            return session.query(VideoClassification).filter(VideoClassification.classified_by == classifier).filter(
                VideoClassification.classification == "N/A").count()

    # This method returns the number of videos classified by a user.
    def get_num_classifications(self, classifier):
        with Session(self.engine) as session:
            return session.query(VideoClassification).filter(VideoClassification.classified_by == classifier).filter(
                VideoClassification.classification != "N/A").count()

    def get_total_classifications(self):
        with Session(self.engine) as session:
            return session.query(func.count(func.distinct(VideoClassification.video_id))) \
                                    .filter(VideoClassification.classification != "N/A") \
                                    .scalar()
    
    def get_total_fatah_classifications(self):
        with Session(self.engine) as session:
            return session.query(func.count(func.distinct(VideoClassification.video_id))) \
                                    .filter(VideoClassification.classification == "Fatah") \
                                    .scalar()

    def get_total_hamas_classifications(self):
        with Session(self.engine) as session:
            return session.query(func.count(func.distinct(VideoClassification.video_id))) \
                                    .filter(VideoClassification.classification == "Hamas") \
                                    .scalar()

    def get_total_none_classifications(self):
            with Session(self.engine) as session:
                return session.query(func.count(func.distinct(VideoClassification.video_id))) \
                                        .filter(VideoClassification.classification == "None") \
                                        .scalar()

    # def get_finished_classifications(self):
    #     # Create a list to store classification data
    #     classifications_data = []
    #
    #     with Session(self.engine) as session:
    #         # Query to get unique tweet IDs with desired classifications
    #         negative_classifications = session.query(
    #             Classification.id,
    #             Classification.tweet,
    #             Classification.classification,
    #             Classification.features,
    #             Tweet.content
    #         ).join(Tweet, Classification.tweet == Tweet.id).filter(Classification.classification == "Positive").distinct(Classification.tweet).all()
    #
    #         # Append classification data to the list
    #         for classification in negative_classifications:
    #
    #             classifications_data.append({
    #                 'id': classification.id,
    #                 'tweet_id': classification.tweet,
    #                 'classification': classification.classification,
    #                 'features': classification.features,
    #                 'tweet': classification.content
    #             })
    #
    #         return classifications_data

