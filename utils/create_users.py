import string
import random

import bcrypt
from db.access import DBAccess


def generate_password(length=6):
    """
    Generates a secure random password of a given length.
    Includes uppercase, lowercase, and digits.
    """
    characters = string.ascii_lowercase + string.digits  # a-z, 0-9
    return ''.join(random.choices(characters, k=length))

# Example usage
print(generate_password())
def create_user(email):
    """
    Creates a new user and returns their raw password.
    """
    db = DBAccess()

    # Generate a password
    password = generate_password()

    # Add the user to the database
    db.add_user(email, password)

    return password

def add_pro_user(email):
    """
    Creates a new pro user.
    """
    db = DBAccess()

    # Generate a password
    password = generate_password()

    # Add the user to the Users table
    user = db.add_user(email, password)

    # If user creation was successful, add them to ProUsers
    if user:
        db.add_pro_user(user["id"])  # Assuming add_pro_user() takes user ID

    return password

def create_multiple_users(email_list):
    """
    Creates multiple users from a list of emails.
    Returns a dictionary mapping emails to generated passwords.
    """
    user_credentials = {}

    for email in email_list:
        password = create_user(email)

        user_credentials[email] = password

    return user_credentials

def main():
    # Create a single user
    # email = "biuproject051@gmail.com"
    # add_pro_user(email)
    # email_list = ["a@a.com", "b@b.com", "c@c.com"]
    # user_credentials = create_multiple_users(email_list)
    db = DBAccess()
    db.assign_videos_to_users()

if __name__ == "__main__":
    main()