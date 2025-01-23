from datetime import datetime

from sqlalchemy import Column, Integer, String, Date, Boolean, ForeignKey
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class Passcode(Base):
    __tablename__ = 'passcodes'
    __table_args__ = {'schema': 'main'}

    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String, unique=True)
    valid_until = Column(Date)
    created = Column(Date)
    activated = Column(Boolean, default=False)
    email = Column(String)
    max_classifications = Column(Integer)
    professional = Column(Boolean, default=False)

    def __repr__(self):
        return f"<Passcode(" \
               f"id={self.id}, key={self.key}," \
               f" valid_until={self.valid_until}," \
               f" created={self.created}," \
               f" activated={self.activated})," \
               f" email={self.email})," \
               f" max_classifications={self.max_classifications})>"
    
    
    def is_valid(self, num_classifications):
        current_date = datetime.now().date()
        return (self.valid_until > current_date and
                self.activated and
                (self.max_classifications is None or num_classifications < self.max_classifications))


class Tweeter(Base):
    __tablename__ = 'tweeters'
    __table_args__ = {'schema': 'main'}

    username = Column(String, primary_key=True)
    

    def __repr__(self):
        return f"<Tweeter(username={self.username})>"


class Tweet(Base):
    __tablename__ = 'tweets'
    __table_args__ = {'schema': 'main'}

    id = Column(String, primary_key=True)
    tweeter = Column(ForeignKey(Tweeter.username))
    content = Column(String)

    def __repr__(self):
        return f"<Tweet(id={self.id})>"


class Classification(Base):
    __tablename__ = 'classifications'
    __table_args__ = {'schema': 'main'}

    id = Column(Integer, primary_key=True, autoincrement=True)
    tweet = Column(ForeignKey(Tweet.id))
    classifier = Column(ForeignKey(Passcode.key))
    classification = Column(String)
    features = Column(String, default="")
    classified_at = Column(Date, default=datetime.now())
    started_classification = Column(Date, default=datetime.now())

    def __repr__(self):
        return f"<Classification(id={self.id}, tweet={self.tweet}, classifier={self.classifier}, classification={self.classification})>"


class ProBank(Base):
    __tablename__ = 'probank'
    __table_args__ = {'schema': 'main'}

    id = Column(Integer, primary_key=True, autoincrement=True)
    tweet = Column(ForeignKey(Tweet.id))
    done = Column(Boolean, default=False)

    def __repr__(self):
        return f"<ProBank(id={self.id}, tweet={self.tweet}, done={self.done})>"

