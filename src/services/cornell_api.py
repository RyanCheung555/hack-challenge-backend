import requests

BASE_URL = "https://classes.cornell.edu/api/2.0"

def get_subjects(roster):
    """
    Fetch all subjects for FA26
    """
    url = f"{BASE_URL}/config/subjects.json"
    params = {"roster": roster}

    response = requests.get(url, params=params)
    response.raise_for_status()

    data = response.json()

    return [item["value"] for item in data["data"]["subjects"]]

def get_classes_for_subject(roster, subject):
    """
    Fetch all classes for a subject
    """
    url = f"{BASE_URL}/search/classes.json"

    params = {
        "roster": roster,
        "subject": subject,
        "acadCareer[]": "UG"
    }

    response = requests.get(url, params=params)
    response.raise_for_status()

    return response.json()