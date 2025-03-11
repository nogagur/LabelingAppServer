from datetime import datetime

from sqlalchemy import Column, Integer, String, Date, Boolean, ForeignKey, BigInteger, Text, DateTime
from sqlalchemy.orm import declarative_base

Base = declarative_base()

# Represents a user in the database
class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(255), unique=True, nullable=False)
    password = Column(String(255), nullable=False)

    def __repr__(self):
        return f"<User(id={self.id}, email={self.email})>"
    
# Represents professional users (subclass of Users)
class ProUser(Base):
    __tablename__ = 'prousers'

    id = Column(Integer, ForeignKey('users.id'), primary_key=True)

    def __repr__(self):
        return f"<ProUser(id={self.id})>"

# Represents features for classifying videos
class Feature(Base):
    __tablename__ = 'features'

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(100), unique=True, nullable=False)

    def __repr__(self):
        return f"<Feature(id={self.id}, title={self.title})>"

# Represents the classification of a TikTok video
class VideoClassification(Base):
    __tablename__ = 'videosclassification'

    id = Column(Integer, primary_key=True, autoincrement=True)
    video_id = Column(BigInteger, ForeignKey('videosmeta.id'))
    classification = Column(String(50), nullable=False) # Classification result
    classified_by = Column(Integer, ForeignKey('users.id'))

    def __repr__(self):
        return f"<VideoClassification(id={self.id}, video_id={self.video_id}, classification={self.classification})>"

# Represents the many-to-many relationship between classifications and features
class VideosClassificationFeature(Base):
    __tablename__ = 'videosclassification_features'

    classification_id = Column(Integer, ForeignKey('videosclassification.id'), primary_key=True)
    feature_id = Column(Integer, ForeignKey('features.id'), primary_key=True)

    def __repr__(self):
        return f"<VideosClassificationFeature(classification_id={self.classification_id}, feature_id={self.feature_id})>"

# Represents a TikTok user
class TiktokUser(Base):
    __tablename__ = 'tiktokusers'

    id = Column(BigInteger, primary_key=True)
    username = Column(String(100))
    nickname = Column(String(100))
    description = Column(Text) # Description/Bio
    region = Column(String(50))
    video_num = Column(Integer, default=0) # Number of videos uploaded
    fans = Column(Integer, default=0) # Number of fans (followers)
    following = Column(Integer, default=0) # Number of users followed
    friends = Column(Integer, default=0) # Number of friends
    likes = Column(Integer, default=0) # Total number of likes
    thumbnail = Column(Text)  # Profile thumbnail URL
    pre_classification = Column(String(50)) # Pre tagging classification

    def __repr__(self):
        return f"<TiktokUser(id={self.id}, username={self.username})>"

# Represents metadata for a TikTok video
class VideoMeta(Base):
    __tablename__ = 'videosmeta'

    id = Column(BigInteger, primary_key=True)
    description = Column(Text) # Video description
    user_id = Column(BigInteger, ForeignKey('tiktokusers.id'))  # Foreign key to the uploader's ID
    play_count = Column(Integer, default=0)
    share_count = Column(Integer, default=0)
    comment_count = Column(Integer, default=0)
    created_at = Column(DateTime) # Video creation timestamp
    duration = Column(Integer) # Video duration in seconds
    height = Column(Integer) # Video resolution height
    width = Column(Integer) # Video resolution width
    video_file = Column(Text)
    video_thumbnail = Column(Text)
    web_url = Column(Text)
    music_id = Column(Integer, ForeignKey('music.id')) # Foreign key to the music in the video

    def __repr__(self):
        return f"<VideoMeta(id={self.id}, description={self.description})>"

# Represents a hashtag used in a TikTok video
class Hashtag(Base):
    __tablename__ = 'hashtags'

    id = Column(Integer, primary_key=True, autoincrement=True)
    content = Column(String(100), unique=True)

    def __repr__(self):
        return f"<Hashtag(id={self.id}, content={self.content})>"

# Represents the many-to-many relationship between videos and hashtags
class VideoMetaHashtag(Base):
    __tablename__ = 'videosmeta_hashtags'

    video_id = Column(BigInteger, ForeignKey('videosmeta.id'), primary_key=True)
    hashtag_id = Column(Integer, ForeignKey('hashtags.id'), primary_key=True)

    def __repr__(self):
        return f"<VideoMetaHashtag(video_id={self.video_id}, hashtag_id={self.hashtag_id})>"

# Represents metadata for music associated with a TikTok video
class Music(Base):
    __tablename__ = 'music'

    id = Column(Integer, primary_key=True)
    name = Column(String(150))
    author = Column(String(100))
    play_link = Column(Text)

    def __repr__(self):
        return f"<Music(id={self.id}, name={self.name})>"

class BrokenVideos(Base):
    __tablename__ = "broken_videos"

    video_id = Column(BigInteger, ForeignKey('videosmeta.id'), primary_key=True)
