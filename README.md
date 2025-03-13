# Server Application

This is the backend server for the application, built using **FastAPI** with **Uvicorn**, and **PostgreSQL** database.

## Features
- User authentication & management
- Database management with PostgreSQL
- API endpoints for handling client requests


## Project Structure

- data/ – Stores configuration files, including a list of features for dynamic loading.

- db/ – Manages database interactions and models.
  * access.py handles database queries. 
  * models.py defines database models.
  * db_init/ contains scripts for initializing the database, including schema creation and inserting scraped data.

- utils/ – Contains helper scripts for user management and parameter loading.

Root files:
* Procfile – Defines process types for Heroku deployment.
* api.py – Main backend API handling requests.
* credentials.py – Manages access credentials, including database connection address.
* requirements.txt – Lists Python dependencies.


## Install Dependencies
```shell
pip install -r requirements.txt 
```

## Running the Server Locally
This application is deployed on Heroku. To run the server locally, execute the main function in api.py .
