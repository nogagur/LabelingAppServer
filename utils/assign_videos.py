from db import access

db = access.DBAccess()
num_videos = 10

db.assign_videos_to_users(num_videos)
