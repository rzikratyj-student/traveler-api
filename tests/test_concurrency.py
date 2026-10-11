import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import httpx
import pytest

BASE_URL = os.getenv("TEST_API_URL", "http://127.0.0.1:8000")


def request(method, path, **kwargs):
    with httpx.Client(
        base_url=BASE_URL,
        timeout=20,
        trust_env=False,
    ) as client:
        return client.request(method, path, **kwargs)


def parallel_requests(method, path, payloads):
    barrier = Barrier(len(payloads))

    def send(payload):
        with httpx.Client(
            base_url=BASE_URL,
            timeout=20,
            trust_env=False,
        ) as client:
            barrier.wait(timeout=20)
            return client.request(method, path, json=payload)

    with ThreadPoolExecutor(max_workers=len(payloads)) as executor:
        return list(executor.map(send, payloads))


@pytest.fixture
def plan():
    response = request(
        "POST",
        "/api/travel-plans",
        json={"title": "Concurrency test", "budget": 100},
    )
    assert response.status_code == 201, response.text
    created = response.json()

    try:
        yield created
    finally:
        response = request(
            "DELETE", f"/api/travel-plans/{created['id']}"
        )
        assert response.status_code == 204, response.text


def test_concurrent_plan_updates(plan):
    path = f"/api/travel-plans/{plan['id']}"
    payloads = [
        {"budget": 200, "version": plan["version"]},
        {"budget": 300, "version": plan["version"]},
    ]

    responses = parallel_requests("PUT", path, payloads)

    assert sorted(r.status_code for r in responses) == [200, 409], [
        (r.status_code, r.text) for r in responses
    ]

    winner = next(r.json() for r in responses if r.status_code == 200)
    loser = next(r.json() for r in responses if r.status_code == 409)

    response = request("GET", path)
    assert response.status_code == 200, response.text
    saved = response.json()

    assert saved["version"] == plan["version"] + 1
    assert saved["budget"] == winner["budget"]
    assert loser["current_version"] == saved["version"]


def test_concurrent_location_creation(plan):
    path = f"/api/travel-plans/{plan['id']}/locations"
    payloads = [{"name": f"Location {i}"} for i in range(10)]

    responses = parallel_requests("POST", path, payloads)

    assert all(r.status_code == 201 for r in responses), [
        (r.status_code, r.text) for r in responses
    ]

    created = [r.json() for r in responses]
    assert len({item["id"] for item in created}) == 10
    assert sorted(item["visit_order"] for item in created) == list(
        range(1, 11)
    )

    response = request("GET", f"/api/travel-plans/{plan['id']}")
    assert response.status_code == 200, response.text
    saved = response.json()["locations"]

    assert len(saved) == 10
    assert [item["visit_order"] for item in saved] == list(range(1, 11))


def test_concurrent_location_updates(plan):
    response = request(
        "POST",
        f"/api/travel-plans/{plan['id']}/locations",
        json={"name": "Museum", "budget": 50, "notes": "Original"},
    )
    assert response.status_code == 201, response.text
    location = response.json()
    path = f"/api/locations/{location['id']}"

    payloads = [
        {"budget": 75, "version": location["version"]},
        {"notes": "Updated", "version": location["version"]},
    ]
    responses = parallel_requests("PUT", path, payloads)

    assert sorted(r.status_code for r in responses) == [200, 409], [
        (r.status_code, r.text) for r in responses
    ]

    winner_index = next(
        i for i, response in enumerate(responses)
        if response.status_code == 200
    )
    loser_index = 1 - winner_index

    response = request("GET", f"/api/travel-plans/{plan['id']}")
    assert response.status_code == 200, response.text
    saved = response.json()["locations"][0]

    assert saved["version"] == 2
    if winner_index == 0:
        assert saved["budget"] == 75
        assert saved["notes"] == "Original"
    else:
        assert saved["budget"] == 50
        assert saved["notes"] == "Updated"

    assert responses[loser_index].json()["current_version"] == 2

    # Retry the rejected change using the current version.
    retry = {**payloads[loser_index], "version": saved["version"]}
    response = request("PUT", path, json=retry)
    assert response.status_code == 200, response.text

    result = response.json()
    assert result["version"] == 3
    assert result["budget"] == 75
    assert result["notes"] == "Updated"