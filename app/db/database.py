from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os

#DATABASE_URL = "mysql+pymysql://root:@127.0.0.1:3306/mewar"
DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL, echo=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

