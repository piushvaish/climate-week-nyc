"""Refresh through a CI secret; on failure the workflow keeps the last deployment."""
import os
from news_service import refresh_news

if __name__=='__main__':
    try:
        result=refresh_news(os.environ.get('TAVILY_API_KEY'))
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from None
    print(f"Retrieved {len(result['stories'])} stories at {result['retrievedAt']}")
