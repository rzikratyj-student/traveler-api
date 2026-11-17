"""Simple load test for a running TravelerAPI server.

Each virtual user (VU) repeats a mixed workload for a fixed time:
  50% GET  /api/travel-plans/{id}
  20% GET  /api/travel-plans          (list of all plans)
  15% PUT  /api/travel-plans/{id}     (read version, then update)
  15% POST /api/travel-plans/{id}/locations

Usage (server must already be running):
  python scripts/load_test.py --users 100 --duration 30 --processes 2
  python scripts/load_test.py --users 1000 --think 5 --duration 60 --processes 3

--think 0 (default): every user sends requests back to back, which is
far heavier than real people. --think N: a pause of 0..2N seconds
(mean N) between actions, a rough model of human users.

One Python process can itself become the bottleneck (100% of one CPU
core); --processes splits the users between several load processes.
Run the load generator on another machine for the most honest numbers.

The script creates its own plans and deletes them at the end.
HTTP 409 on PUT is an expected optimistic-locking result, so it is
counted separately and not as an error.
"""
import argparse
import asyncio
from concurrent.futures import ProcessPoolExecutor
import os
import random
import statistics
import time
from collections import Counter, defaultdict

import httpx


def percentile(values, p):
    if not values:
        return float("nan")
    values = sorted(values)
    index = min(len(values) - 1, round(p / 100 * (len(values) - 1)))
    return values[index]


async def timed(client, stats, name, method, url, **kwargs):
    start = time.perf_counter()
    try:
        response = await client.request(method, url, **kwargs)
        status = response.status_code
    except httpx.HTTPError as error:
        response, status = None, type(error).__name__
    stats[name].append((time.perf_counter() - start) * 1000)
    stats["status"].append((name, status))
    return response


async def virtual_user(client, plan_ids, stats, stop_at, think):
    if think:
        # Spread the start so users do not all fire at once.
        await asyncio.sleep(random.uniform(0, 2 * think))
    while time.perf_counter() < stop_at:
        plan_id = random.choice(plan_ids)
        roll = random.random()
        if roll < 0.50:
            await timed(client, stats, "GET plan", "GET",
                        f"/api/travel-plans/{plan_id}")
        elif roll < 0.70:
            await timed(client, stats, "GET list", "GET",
                        "/api/travel-plans")
        elif roll < 0.85:
            plan = await timed(client, stats, "GET plan", "GET",
                               f"/api/travel-plans/{plan_id}")
            if plan is not None and plan.status_code == 200:
                await timed(
                    client, stats, "PUT plan", "PUT",
                    f"/api/travel-plans/{plan_id}",
                    json={"budget": random.randint(1, 9999),
                          "version": plan.json()["version"]},
                )
        else:
            await timed(client, stats, "POST location", "POST",
                        f"/api/travel-plans/{plan_id}/locations",
                        json={"name": "Load test location"})
        if think:
            # A real person pauses between actions ("think time").
            await asyncio.sleep(random.uniform(0, 2 * think))


async def run_users(url, plan_ids, users, duration, think):
    limits = httpx.Limits(max_connections=users,
                          max_keepalive_connections=users)
    stats = defaultdict(list)
    async with httpx.AsyncClient(base_url=url, timeout=60,
                                 limits=limits, trust_env=False) as client:
        stop_at = time.perf_counter() + duration
        await asyncio.gather(*(
            virtual_user(client, plan_ids, stats, stop_at, think)
            for _ in range(users)
        ))
    return dict(stats)


def run_process(url, plan_ids, users, duration, think):
    return asyncio.run(run_users(url, plan_ids, users, duration, think))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default=os.getenv(
        "TEST_API_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--users", type=int, default=100)
    parser.add_argument("--duration", type=float, default=30)
    parser.add_argument("--plans", type=int, default=50)
    parser.add_argument("--processes", type=int, default=1)
    parser.add_argument(
        "--think", type=float, default=0,
        help="mean pause in seconds between a user's actions "
             "(0 = no pause, maximum pressure)",
    )
    args = parser.parse_args()

    with httpx.Client(base_url=args.url, timeout=60,
                      trust_env=False) as client:
        plan_ids = []
        for i in range(args.plans):
            response = client.post("/api/travel-plans",
                                   json={"title": f"Load test {i}"})
            response.raise_for_status()
            plan_ids.append(response.json()["id"])

        shares = [args.users // args.processes] * args.processes
        for i in range(args.users % args.processes):
            shares[i] += 1

        started = time.perf_counter()
        with ProcessPoolExecutor(args.processes) as pool:
            results = list(pool.map(
                run_process,
                [args.url] * args.processes,
                [plan_ids] * args.processes,
                shares,
                [args.duration] * args.processes,
                [args.think] * args.processes,
            ))
        elapsed = time.perf_counter() - started

        for plan_id in plan_ids:
            client.delete(f"/api/travel-plans/{plan_id}")

    stats = defaultdict(list)
    for result in results:
        for name, values in result.items():
            stats[name].extend(values)

    statuses = stats.pop("status")
    all_times = [t for times in stats.values() for t in times]
    counts = Counter(statuses)
    errors = sum(n for (name, status), n in counts.items()
                 if not (status in (200, 201)
                         or (name == "PUT plan" and status == 409)))

    print(f"users={args.users} processes={args.processes} "
          f"think={args.think}s "
          f"duration={elapsed:.1f}s "
          f"plans={args.plans} requests={len(all_times)} "
          f"throughput={len(all_times) / elapsed:.0f} req/s")
    print(f"{'operation':<14}{'count':>7}{'p50 ms':>9}{'p95 ms':>9}"
          f"{'p99 ms':>9}{'max ms':>9}")
    for name, times in sorted(stats.items()) + [("ALL", all_times)]:
        print(f"{name:<14}{len(times):>7}"
              f"{statistics.median(times):>9.1f}"
              f"{percentile(times, 95):>9.1f}"
              f"{percentile(times, 99):>9.1f}{max(times):>9.1f}")
    print("statuses:", dict(sorted(counts.items(), key=str)))
    print(f"unexpected errors: {errors}")


if __name__ == "__main__":
    main()
