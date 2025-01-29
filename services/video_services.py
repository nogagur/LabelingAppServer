from db.access import DBAccess

def get_video(video_id):
    """
    Retrieves a video from the database using its ID.
    Returns the video object if found, otherwise None.
    """
    db = DBAccess()
    return db.get_video_by_id(video_id)

def get_video_for_classification(user_id):
    """
    Retrieves a video for classification by a user.
    Ensures the user does not get a video they already classified.
    """
    db = DBAccess()
    return db.get_video_for_user(user_id)

def classify_video(user_id, video_id, classification, features):
    """
    Handles video classification by a user.
    """
    db = DBAccess()
    return db.classify_video(video_id, user_id, classification, features)
