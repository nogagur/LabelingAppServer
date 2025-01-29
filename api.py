import inspect
from datetime import datetime, timedelta

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from pydantic import BaseModel
from asyncio.locks import Lock

from credentials import JWT_SECRET_KEY
from db.access import DBAccess
from utils.load_params import load_params

app = FastAPI()
auth = HTTPBearer()

params = load_params()
lock = Lock()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"], 
    allow_headers=["*"],
)


def generate_token(key: str):
    # Set the token expiration time
    expire = datetime.utcnow() + timedelta(hours=3)
    # Create the payload containing the key
    payload = {"key": key, "exp": expire}
    # Generate the JWT token
    token = jwt.encode(payload, JWT_SECRET_KEY, algorithm="HS256")
    return token


def login_required(func):
    async def wrapper(credentials: HTTPAuthorizationCredentials = Depends(auth), *args, **kwargs):
        try:
            # Verify and decode the token
            payload = jwt.decode(credentials.credentials, JWT_SECRET_KEY, algorithms=["HS256"])
            key = payload.get("key")
            if key:
                # Process the request with the authenticated key
                return await func(passcode=key, *args, **kwargs)
            else:
                raise HTTPException(status_code=401, detail="Invalid token")
        except JWTError:
            raise HTTPException(status_code=401, detail="Invalid token")

    wrapper.__name__ = func.__name__
    wrapper.__doc__ = func.__doc__

    params = list(inspect.signature(func).parameters.values()) + list(inspect.signature(wrapper).parameters.values())
    wrapper.__signature__ = inspect.signature(func).replace(
        parameters=[
            # Use all parameters from handler
            *filter(lambda p: p.name != 'passcode', inspect.signature(func).parameters.values()),

            # Skip *args and **kwargs from wrapper parameters:
            *filter(
                lambda p: p.kind not in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD),
                inspect.signature(wrapper).parameters.values()
            )
        ]
    )

    return wrapper


class Passcode(BaseModel):
    passcode: str


@app.post("/auth/signin")
async def signin(passcode: Passcode):
    db = DBAccess()
    passcode = passcode.passcode
    passcode = db.get_passcode(passcode)
    if passcode is None:
        raise HTTPException(status_code=401, detail="Unauthorized")
    if not passcode.is_valid(db.get_num_classifications(passcode.key)):
        raise HTTPException(status_code=401, detail="Unauthorized")
    token = generate_token(passcode.key)
    return {'token': token, 'is_pro': passcode.professional}


@app.get("/get_tweet")
@login_required
async def get_tweet(passcode):
    async with lock:
        db = DBAccess()
        tweet = db.get_unclassified_tweet(passcode)
        if tweet is not None:
            db.update_start(tweet, passcode)

    if tweet is not None:
        return {'id': tweet.id, 'tweeter': tweet.tweeter, 'content': tweet.content}
    else:
        return {'error': 'No unclassified tweets'}
    
class SkipTweetRequest(BaseModel):
    curr_id: str
    
@app.post("/get_skip_tweet")
@login_required
async def get_skip_tweet(passcode, request: SkipTweetRequest):
    curr_id = request.curr_id
    # TODO: delete next line.
    print(f"curr_id: {curr_id}")
    async with lock:
        db = DBAccess()
        if db.get_passcode(passcode).professional:
            tweet = db.get_different_unclassified_tweet_pro(passcode)
            if tweet is None:
                tweet = db.get_different_unclassified_tweet(passcode, curr_id)
        else:
            tweet = db.get_different_unclassified_tweet(passcode, curr_id)

        if tweet is not None:
            db.update_start(tweet, passcode)
            return {'id': tweet.id, 'tweeter': tweet.tweeter, 'content': tweet.content}
        else:
            tweet = db.get_video_by_id(curr_id)
            return {'id': tweet.id, 'tweeter': tweet.tweeter, 'content': tweet.content}


class Classification(BaseModel):
    classification: str
    tweet_id: str
    features: str


@app.post("/classify_tweet")
@login_required
async def classify_tweet(passcode, classification: Classification):
    db = DBAccess()
    if not db.get_passcode(passcode).is_valid(db.get_num_classifications(passcode)):
        raise HTTPException(status_code=401, detail="Unauthorized")
    tweet = db.get_video_by_id(classification.tweet_id)
    if tweet is not None:
        if classification.classification not in ['Positive', 'Negative', 'Irrelevant', 'Unknown']:
            return {'error': 'Invalid classification'}
        async with lock:
            result = db.classify_tweet(classification.tweet_id, passcode, classification.classification,
                                       classification.features)
        return {'classified': result}
    else:
        return {'error': 'No such tweet'}


@app.get("/count_classifications")
@login_required
async def count_classifications(passcode):
    db = DBAccess()
    result = db.get_num_classifications(passcode)
    return {"count": result}

@app.get("/get_user_panel")
@login_required
async def get_user_panel(passcode):
    async with lock:
        db = DBAccess()
        num_classified = db.get_num_classifications(passcode)
        num_pos = db.get_num_positive_classifications(passcode)
        num_neg = db.get_num_negative_classifications(passcode)
        time_left = db.get_time_left(passcode)
        num_remain = db.get_num_remaining_classifications(passcode)
        avg_time = db.get_average_classification_time(passcode)
        num_irr = db.get_num_irrelevant_classifications(passcode)

    # Calculate average time in seconds (for demonstration purposes)
    if avg_time is not None:
        average_time_seconds = f"{avg_time:.2f}"
    else:
        average_time_seconds = "N/A"
        
    if num_classified is not None:
        return {'total': num_classified,
                'pos': num_pos,
                'neg': num_neg,
                'time': time_left,
                'remain': num_remain,
                'avg': average_time_seconds,
                'irr': num_irr}
    else:
        return {'error': 'Error getting user data'}


@app.get("/get_pro_panel")
@login_required
async def get_pro_panel(passcode):
    users = []
    async with lock:
        db = DBAccess()
        user_data = db.get_users()
        num_tot = db.get_total_classifications()
        tot_neg = db.get_total_negative_classifications()
        tot_pos = db.get_total_positive_classifications()
        tot_irr = db.get_total_irrelevant_classifications()


        for user in user_data:
            curr_pass = user.key
            email = user.email
            num_classified = db.get_num_classifications(curr_pass)
            num_pos = db.get_num_positive_classifications(curr_pass)
            num_irr = db.get_num_irrelevant_classifications(curr_pass)
            num_neg = db.get_num_negative_classifications(curr_pass)
            avg_time = db.get_average_classification_time(curr_pass)
            
            if num_classified is not None:

                # Calculate average time in seconds (for demonstration purposes)
                if avg_time is not None:
                    average_time_seconds = f"{avg_time:.2f}"
                else:
                    average_time_seconds = "N/A"

                # Append user data to the list
                users.append({
                    "email": email,
                    "personalClassifications": num_classified,
                    "positiveClassified": num_pos,
                    "negativeClassified": num_neg,
                    "averageTime": average_time_seconds,
                    "irrelevantClassified":num_irr
                })
            else:
                # Handle error case if data retrieval fails for the user
                users.append({
                    "email": email,
                    "error": "Error getting user data"
                })

    return {"users": users,
            "total": num_tot,
            "total_pos": tot_pos,
            "total_neg": tot_neg,
            "total_irr": tot_irr}


@app.get("/params_list")
async def params_list():
    # We will make the list of parameters dynamic, so that we can add/remove parameters without changing the web client.
    # Each is boolean.

    return params


if __name__ == '__main__':
    import uvicorn

    uvicorn.run(app, host="localhost", port=8000)
