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
            user = session.query(User).filter(User.id == user_id).one_or_none()
            return user

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
        Retrieves a video assigned to the user that is still unclassified.
        If the user has no assigned videos left, return None.
        """

        with Session(self.engine) as session:
            # Fetch an unclassified video assigned to this user
            video_entry = session.query(VideoMeta).join(
                VideoClassification, VideoMeta.id == VideoClassification.video_id
            ).filter(
                VideoClassification.classified_by == user_id,
                VideoClassification.classification == "N/A"
            ).order_by(func.random()).first()  # Pick a random assigned video

            if not video_entry:
                print(f"No unclassified videos left for user {user_id}.")
                return None

            # Fully load attributes before session closes
            _ = video_entry.id, video_entry.video_file, video_entry.description
            return video_entry

    def assign_videos_to_users(self, max_videos_per_user=10):
        """
        Assigns videos randomly to non-pro users while ensuring:
        - Each video is assigned to exactly 2 users (if possible).
        - Each user gets assigned up to `max_videos_per_user`.
        - If needed, some videos are assigned to only 1 user to reach max limit per user.
        """

        with Session(self.engine) as session:
            # Fetch videos that are assigned to less than 2 users
            partially_assigned_videos = session.query(VideoMeta.id).outerjoin(
                VideoClassification, VideoMeta.id == VideoClassification.video_id
            ).group_by(VideoMeta.id).having(func.count(VideoClassification.video_id) < 2).all()

            partially_assigned_videos = [v[0] for v in partially_assigned_videos]
            random.shuffle(partially_assigned_videos)  # Shuffle video order

            # Get all non-pro users
            non_pro_users = session.query(User.id).filter(
                ~User.id.in_(session.query(ProUser.id))
            ).all()

            non_pro_users = [u[0] for u in non_pro_users]
            random.shuffle(non_pro_users)  # Shuffle users for fairness

            # Track user assignments
            user_video_count = {user: 0 for user in non_pro_users}
            user_video_map = {user: [] for user in non_pro_users}

            assigned_videos = set()  # Track videos fully assigned

            # Assign videos to users
            for video_id in partially_assigned_videos:
                assigned_count = session.query(VideoClassification).filter(
                    VideoClassification.video_id == video_id
                ).count()

                if assigned_count >= 2:
                    continue  # Skip already fully assigned videos

                # Get eligible users who need more videos
                eligible_users = [u for u in non_pro_users if user_video_count[u] < max_videos_per_user]

                if not eligible_users:
                    break  # Stop if no users need more videos

                # Choose up to 2 users (but ensure no video goes over 2 assignments)
                selected_users = random.sample(eligible_users, min(2 - assigned_count, len(eligible_users)))

                for user_id in selected_users:
                    session.add(VideoClassification(video_id=video_id, classified_by=user_id, classification="N/A"))
                    user_video_map[user_id].append(video_id)
                    user_video_count[user_id] += 1

                # Mark video as fully assigned if it reached 2 users
                if session.query(VideoClassification).filter(VideoClassification.video_id == video_id).count() == 2:
                    assigned_videos.add(video_id)

            # Ensure every user gets `max_videos_per_user' videos
            remaining_users = [u for u in non_pro_users if user_video_count[u] < max_videos_per_user]
            unassigned_videos = [v for v in partially_assigned_videos if v not in assigned_videos]
            random.shuffle(unassigned_videos)

            while remaining_users and unassigned_videos:
                for user in remaining_users:
                    if user_video_count[user] >= max_videos_per_user:
                        continue  # Skip users who reached max quota

                    if not unassigned_videos:
                        break  # Stop if there are no videos left

                    video_id = unassigned_videos.pop()
                    session.add(VideoClassification(video_id=video_id, classified_by=user, classification="N/A"))
                    user_video_map[user].append(video_id)
                    user_video_count[user] += 1

                    if user_video_count[user] >= max_videos_per_user:
                        remaining_users.remove(user)

            session.commit()
            print(f"Assigned videos. Each user received up to {max_videos_per_user} videos.")
            return user_video_map  # Optional debug output

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
            if features:
                self.add_classification_features(classification_entry.id, features, session)

            # Detect if a pro user is needed due to conflict or "uncertain" classification
            if not self.is_pro_user(user_id):
                self.check_if_pro_needed(session, video_id)

            session.commit()
            return classification_entry

    def is_pro_user(self, user_id):
        with Session(self.engine) as session:
            return session.query(ProUser).filter(ProUser.id == user_id).one_or_none()

    def add_classification_features(self, classification_id, features, session):
        """
        Adds the features selected in the classification to the VideosClassification_Features table.
        """
        for feature_id, is_selected in features.items():
            if is_selected:  # Only add features that are marked as True
                # Ensure the feature exists in the Features table
                feature_obj = session.query(Feature).filter(Feature.id == feature_id).one_or_none()
                if not feature_obj:
                    raise ValueError(f"Feature with ID '{feature_id}' does not exist.")

                # Insert into VideosClassification_Features table
                feature_entry = VideosClassificationFeature(
                    classification_id=classification_id,
                    feature_id=feature_id
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

        # If there are two different classifications OR 'uncertain' is present OR 'irrelevant' is present
        if len(classifications) > 1 or "Uncertain" in classifications or "Irrelevant" in classifications:
            # Check if a pro classification already exists
            pro_entry = session.query(VideoClassification).join(
                ProUser, VideoClassification.classified_by == ProUser.id
            ).filter(
                VideoClassification.video_id == video_id,
                VideoClassification.classification == "N/A"
            ).one_or_none()

            if not pro_entry:
                # Get all pro user IDs
                pro_users = session.query(ProUser.id).order_by(ProUser.id).all()
                pro_users = [p[0] for p in pro_users]  # Convert to list of IDs

                if not pro_users:
                    print("No pro users available.")
                    return

                next_pro_user = self.next_pro_to_assign(pro_users, session)

                # Insert new classification for the pro user
                pro_classification = VideoClassification(
                    video_id=video_id,
                    classified_by=next_pro_user,
                    classification="N/A"
                )
                session.add(pro_classification)
                session.commit()
                print(f"Assigned video {video_id} to pro user {next_pro_user} for review.")

    def next_pro_to_assign(self, pro_users, session):
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

    # This method return the number of videos classified as uncertain which organization, by a user.
    def get_num_uncertain_by_user(self, classifier):
        with Session(self.engine) as session:
            return session.query(VideoClassification).filter(VideoClassification.classified_by == classifier).filter(
                VideoClassification.classification == "Uncertain").count()

    # This method return the number of videos classified as irrelevant which organization, by a user.
    def get_num_irrelevant_by_user(self, classifier):
        with Session(self.engine) as session:
            return session.query(VideoClassification).filter(
                VideoClassification.classified_by == classifier).filter(
                VideoClassification.classification == "Irrelevant").count()

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

    def get_total_uncertain_classifications(self):
        with Session(self.engine) as session:
            return session.query(func.count(func.distinct(VideoClassification.video_id))) \
                .filter(VideoClassification.classification == "Uncertain") \
                .scalar()

    def get_total_irrelevant_classifications(self):
        with Session(self.engine) as session:
            return session.query(func.count(func.distinct(VideoClassification.video_id))) \
                .filter(VideoClassification.classification == "Irrelevant") \
                .scalar()

