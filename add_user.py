from db.access import DBAccess

db = DBAccess()
emails = ['']
num_days = 21
for email in emails:
    passcode = db.create_passcode(email,num_days)
    print(f"Passcode created successfully for user '{email}': {passcode}")




