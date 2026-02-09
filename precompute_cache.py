import time

from app import get_cached_variants, save_result, solve_instance


def main():
    locations_min = 12
    locations_max = 12
    teams_min = 24
    teams_max = 24

    total = 0
    saved = 0
    cached = 0
    no_solution = 0
    durations = []
    target_variants = 5
    max_attempts_per_combo = 12

    for locations in range(locations_min, locations_max + 1):
        for teams in range(teams_min, teams_max + 1, 2):
            if teams > 2 * locations:
                continue
            total += 1
            print(f"Working on locations={locations}, teams={teams}...", flush=True)
            start = time.perf_counter()
            variants = get_cached_variants(locations, teams)
            if len(variants) >= target_variants:
                cached += 1
                elapsed = time.perf_counter() - start
                durations.append((locations, teams, "cached", elapsed))
                print(f"  cached, skip ({elapsed:.2f}s)", flush=True)
                continue

            existing_rounds = [v["rounds_data"] for v in variants]
            added = 0
            attempts = 0
            while len(existing_rounds) < target_variants and attempts < max_attempts_per_combo:
                attempts += 1
                seed = (time.time_ns() % 2147483647) + attempts
                solved = solve_instance(locations, teams, seed)
                if not solved:
                    continue
                if solved["rounds"] in existing_rounds:
                    continue
                save_result(
                    locations,
                    teams,
                    solved["rounds"],
                    solved["repeats"],
                    solved["repeats_detail"],
                )
                existing_rounds.append(solved["rounds"])
                saved += 1
                added += 1

            elapsed = time.perf_counter() - start
            if added > 0:
                status = f"saved {added}/{target_variants}"
            elif len(existing_rounds) == 0:
                no_solution += 1
                status = "no_solution"
            else:
                status = f"partial {len(existing_rounds)}/{target_variants}"
            durations.append((locations, teams, status, elapsed))
            print(f"  {status} ({elapsed:.2f}s)", flush=True)

    print("\nSummary", flush=True)
    print(f"  total: {total}", flush=True)
    print(f"  saved: {saved}", flush=True)
    print(f"  cached: {cached}", flush=True)
    print(f"  no solution: {no_solution}", flush=True)
    print("\nTiming by combination", flush=True)
    for locations, teams, status, elapsed in durations:
        print(f"  L={locations}, T={teams}: {status} ({elapsed:.2f}s)", flush=True)


if __name__ == "__main__":
    main()
