import bcrypt
from db.access import DBAccess

def generate_password():
    """
    Generates a secure random password.
    """
    return bcrypt.gensalt().decode()[:12]  # Random 12-character password


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

def validate_user(email, password):
    """
    Validates a user's email and password.
    Returns the user object if valid, otherwise None.
    """
    db = DBAccess()
    return db.validate_user(email, password)
