import os

import pandas as pd
from sqlalchemy import create_engine, text

APP_DB_HOST = os.environ.get("APP_DB_HOST")
APP_DB_NAME = os.environ.get("APP_DB_NAME")
APP_DB_USERNAME = os.environ.get("APP_DB_USERNAME")
APP_DB_PASSWORD = os.environ.get("APP_DB_PASSWORD")
APP_DB_PORT = os.environ.get("APP_DB_PORT")
APP_DATABASE_URL = f"postgresql://{APP_DB_USERNAME}:{APP_DB_PASSWORD}@{APP_DB_HOST}:{APP_DB_PORT}/{APP_DB_NAME}"
TIMEZONE = os.environ.get("TIMEZONE")

engine = create_engine(APP_DATABASE_URL, pool_pre_ping=True)

def fetch_df(query: str, params: dict | None = None) -> pd.DataFrame:

    with engine.connect() as conn:
        result = conn.execute(text(query), params or {})
        df = pd.DataFrame(result.fetchall(), columns=list(result.keys()))
    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            if df[col].dt.tz is None:
                df[col] = df[col].dt.tz_localize("UTC")
            df[col] = df[col].dt.tz_convert(TIMEZONE)
    return df
