from db import access

db = access.DBAccess()
num_videos = 200

# db.assign_videos_to_users(num_videos)

# db.assign_videos_prioritizing_hamas(200, 500)

db.assign_remaining_hamas_videos([18])
