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


class User(BaseModel):
    password: str


@app.post("/auth/signin")
async def signin(user: User):
    db = DBAccess()
    user = user.password
    user = db.validate_user(user)
    if user is None:
        raise HTTPException(status_code=401, detail="Unauthorized")
    token = generate_token(user.id)

    return {'token': token, 'is_pro': user.id in db.get_pro_users()}


@app.get("/get_video")
@login_required
async def get_video(user_id):
    async with lock:
        db = DBAccess()
        video = db.get_video_for_user(user_id)

    if video is not None:
        username = db.get_uploader_username(video.id)
        return {'id': video.id, 'uploader': username, 'file': video.video_file}
    else:
        return {'error': 'No unclassified videos'}
    
class SkipTweetRequest(BaseModel):
    curr_id: str

# TODO: currently no matching db function
# @app.post("/get_skip_tweet")
# @login_required
# async def get_skip_tweet(passcode, request: SkipTweetRequest):
#     curr_id = request.curr_id
#     async with lock:
#         db = DBAccess()
#         if db.get_passcode(passcode).professional:
#             tweet = db.get_different_unclassified_tweet_pro(passcode)
#             if tweet is None:
#                 tweet = db.get_different_unclassified_tweet(passcode, curr_id)
#         else:
#             tweet = db.get_different_unclassified_tweet(passcode, curr_id)
#
#         if tweet is not None:
#             db.update_start(tweet, passcode)
#             return {'id': tweet.id, 'tweeter': tweet.tweeter, 'content': tweet.content}
#         else:
#             tweet = db.get_video_by_id(curr_id)
#             return {'id': tweet.id, 'tweeter': tweet.tweeter, 'content': tweet.content}


class Classification(BaseModel):
    classification: str
    video_id: str
    features: str


@app.post("/classify_video")
@login_required
async def classify_video(user_id, classification: Classification):
    db = DBAccess()
    video = db.get_video_by_id(classification.video_id)
    if video is not None:
        if classification.classification not in ['Hamas', 'Fatah', 'None', 'Uncertain']:
            return {'error': 'Invalid classification'}
        async with lock:
            result = db.classify_video(classification.video_id, user_id, classification.classification,
                                       classification.features)
        return {'classified': result}
    else:
        return {'error': 'No such video'}


@app.get("/count_classifications")
@login_required
async def count_classifications(user_id):
    db = DBAccess()
    result = db.get_num_classifications(user_id)
    return {"count": result}

@app.get("/get_user_panel")
@login_required
async def get_user_panel(user_id):
    async with lock:
        db = DBAccess()
        num_classified = db.get_num_classifications(user_id)
        num_fatah = db.get_num_fatah_by_user(user_id)
        num_hamas = db.get_num_hamas_by_user(user_id)
        num_none = db.get_num_none_by_user(user_id)
        num_remain = db.get_num_remaining_classifications(user_id)

    if num_classified is not None:
        return {'total': num_classified,
                'fatah': num_fatah,
                'hamas': num_hamas,
                'none': num_none,
                'remain': num_remain}
    else:
        return {'error': 'Error getting user data'}


@app.get("/get_pro_panel")
@login_required
async def get_pro_panel(user_id):
    users = []
    async with lock:
        db = DBAccess()
        user_data = db.get_all_users()
        num_tot = db.get_total_classifications()
        tot_fatah = db.get_total_fatah_classifications()
        tot_hamas = db.get_total_hamas_classifications()
        tot_none = db.get_total_none_classifications()


        for user in user_data:
            curr_user = user.id
            email = user.email
            num_classified = db.get_num_classifications(curr_user)
            num_fatah = db.get_num_fatah_by_user(curr_user)
            num_hamas = db.get_num_hamas_by_user(curr_user)
            num_none = db.get_num_none_by_user(curr_user)

            if num_classified is not None:

                # Append user data to the list
                users.append({
                    "email": email,
                    "personalClassifications": num_classified,
                    "fatahClassified": num_fatah,
                    "hamasClassified": num_hamas,
                    "noneClassified":num_none
                })
            else:
                # Handle error case if data retrieval fails for the user
                users.append({
                    "email": email,
                    "error": "Error getting user data"
                })

    return {"users": users,
            "total": num_tot,
            "total_hamas": tot_hamas,
            "total_fatah": tot_fatah,
            "total_none": tot_none}


@app.get("/params_list")
async def params_list():
    # We will make the list of parameters dynamic, so that we can add/remove parameters without changing the web client.
    # Each is boolean.
    # TODO: update features list, maybe need different logic
    return params


if __name__ == '__main__':
    import uvicorn

    uvicorn.run(app, host="localhost", port=8000)
