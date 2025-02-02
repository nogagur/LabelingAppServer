from dotenv import load_dotenv
import os

load_dotenv()

DB = f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT', '5432')}/{os.getenv('DB_NAME')}"

JWT_SECRET_KEY = "my secret key"

