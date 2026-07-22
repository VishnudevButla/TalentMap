import requests
from app.config import settings

def test_adzuna():
    url = f"{settings.ADZUNA_BASE_URL}/jobs/us/search/1"
    params = {
        "app_id": settings.ADZUNA_APP_ID,
        "app_key": settings.ADZUNA_APP_KEY,
        "results_per_page": 5,
        "what": "software engineer",
    }
    resp = requests.get(url, params=params)
    resp.raise_for_status()
    data = resp.json()
    print(f"Got {len(data['results'])} jobs")
    print(data["results"][0])  # peek at one job's shape

if __name__ == "__main__":
    test_adzuna()