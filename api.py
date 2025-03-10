from asyncio.locks import Lock
from datetime import datetime, timedelta
from typing import Optional, Dict

from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer
from jose import jwt, JWTError
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError
from pydantic import BaseModel

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

ALGORITHM = "HS256"  # Algorithm used for encoding/decoding the token


def generate_token(user_id):
    # # Set the token expiration time
    # expire = datetime.utcnow() + timedelta(hours=3)
    # Create the payload containing the key
    payload = {"user_id": user_id}
    # Generate the JWT token
    token = jwt.encode(payload, JWT_SECRET_KEY, algorithm="HS256")
    return token


def extract_user_from_token(request: Request) -> Optional[dict]:
    """
    Extracts and verifies the JWT token from the Authorization header.
    Returns the user object if valid, otherwise raises an HTTPException.
    """
    db = DBAccess()

    # Get Authorization header
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authorization token")

    # Extract the token
    token = auth_header.split("Bearer ")[1]

    try:
        # Decode the token using the imported SECRET_KEY and ALGORITHM
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("user_id")  # Ensure the token contains user_id

        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")

        # Fetch user from the database
        user = db.get_user_by_id(user_id)  # Assuming a method exists to fetch user by ID

        if user is None:
            raise HTTPException(status_code=401, detail="User not found")

        return user

    except ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


# Dependency to extract the user from the token
def get_current_user(request: Request):
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authorization token")

    token = auth_header.split("Bearer ")[1]
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("user_id")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token: no user_id")

        db = DBAccess()  # Ensure your DBAccess class is set up properly
        user = db.get_user_by_id(user_id)
        if user is None:
            raise HTTPException(status_code=401, detail="User not found")

        return user
    except ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")


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

    return {'user_id':user.id,'token': token, 'is_pro': user.id in db.get_pro_users()}


@app.get("/get_video")
async def get_video(current_user = Depends(get_current_user)):
    user_id = current_user.id

    async with lock:
        db = DBAccess()
        video = db.get_video_for_user(user_id)

    if video is not None:
        username = db.get_uploader_username(video.id)
        return {
            'id': str(video.id),
            'uploader': username,
            'file': video.video_file,
            'description': video.description,
            'web_url': video.web_url
        }
    else:
        return {'error': 'No unclassified videos'}
    

class Classification(BaseModel):
    classification: str
    video_id: str
    features: Dict[str, bool]


@app.post("/classify_video")
async def classify_video( classification: Classification, current_user = Depends(get_current_user)):
    user_id = current_user.id
    db = DBAccess()
    video = db.get_video_by_id(classification.video_id)
    if video is not None:
        if classification.classification not in ['Hamas', 'Fatah', 'Unaffiliated', 'Uncertain', 'Broken']:
            return {'error': 'Invalid classification'}
        async with lock:
            result = db.classify_video(classification.video_id, user_id, classification.classification,
                                       classification.features)
        return {'classified': result}
    else:
        return {'error': 'No such video'}


@app.get("/count_classifications")
async def count_classifications(current_user = Depends(get_current_user)):
    user_id = current_user.id
    db = DBAccess()
    classifications_done= db.get_num_classifications(user_id)
    classifications_left = db.get_num_remaining_classifications(user_id)
    return {"done": classifications_done, "left": classifications_left}

@app.get("/get_user_panel")
async def get_user_panel(current_user = Depends(get_current_user)):
    user_id = current_user.id
    async with lock:
        db = DBAccess()
        num_classified = db.get_num_classifications(user_id)
        num_fatah = db.get_num_fatah_by_user(user_id)
        num_hamas = db.get_num_hamas_by_user(user_id)
        num_unaffiliated = db.get_num_unaffiliated_by_user(user_id)
        num_uncertain = db.get_num_uncertain_by_user(user_id)
        num_broken = db.get_num_broken_by_user(user_id)
        num_remain = db.get_num_remaining_classifications(user_id)

    if num_classified is not None:
        return {'total': num_classified,
                'fatah': num_fatah,
                'hamas': num_hamas,
                'unaffiliated': num_unaffiliated,
                'uncertain': num_uncertain,
                'broken': num_broken,
                'remain': num_remain}
    else:
        return {'error': 'Error getting user data'}


@app.get("/get_pro_panel")
async def get_pro_panel():
    users = []
    async with lock:
        db = DBAccess()
        user_data = db.get_all_users()
        num_tot = db.get_total_classifications()
        tot_fatah = db.get_total_fatah_classifications()
        tot_hamas = db.get_total_hamas_classifications()
        tot_unaffiliated = db.get_total_unaffiliated_classifications()
        tot_uncertain = db.get_total_uncertain_classifications()
        tot_broken = db.get_total_broken_classifications()


        for user in user_data:
            curr_user = user.id
            email = user.email
            num_classified = db.get_num_classifications(curr_user)
            num_fatah = db.get_num_fatah_by_user(curr_user)
            num_hamas = db.get_num_hamas_by_user(curr_user)
            num_unaffiliated = db.get_num_unaffiliated_by_user(curr_user)
            num_uncertain = db.get_num_uncertain_by_user(curr_user)
            num_broken = db.get_num_broken_by_user(curr_user)

            if num_classified is not None:

                # Append user data to the list
                users.append({
                    "email": email,
                    "personalClassifications": num_classified,
                    "fatahClassified": num_fatah,
                    "hamasClassified": num_hamas,
                    "unaffiliatedClassified":num_unaffiliated,
                    "uncertainClassified": num_uncertain,
                    "brokenClassified": num_broken,
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
            "total_unaffiliated": tot_unaffiliated,
            "total_uncertain": tot_uncertain,
            "total_broken": tot_broken,}


@app.get("/params_list")
async def params_list():
    return params


if __name__ == '__main__':
    import uvicorn

    uvicorn.run(app, host="localhost", port=8000)
