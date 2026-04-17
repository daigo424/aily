import pandas as pd
from sqlalchemy import create_engine, text

from packages.core.config import settings

engine = create_engine(settings.app_database_url, pool_pre_ping=True)


def fetch_df(query: str, params: dict | None = None) -> pd.DataFrame:
    with engine.connect() as conn:
        result = conn.execute(text(query), params or {})
        df = pd.DataFrame(result.fetchall(), columns=list(result.keys()))
    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            if df[col].dt.tz is None:
                df[col] = df[col].dt.tz_localize("UTC")
            df[col] = df[col].dt.tz_convert(settings.timezone)
    return df
