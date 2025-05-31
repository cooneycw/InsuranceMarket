import time
import ray
from config.config import Config
from src_code.utils.utils import redis_game_start, redis_game_stop, ins_time, pretend_web_input
from src_code.game.start_game import Game
from src_code.models.db_utils import load_games

# ensure setup.py run first if market code has changed

# Constants for game management
MAX_GAME_DURATION = 60 * 60 * 3  # 2 hours in seconds - adjust based on your expected max game time
STATUS_POLL_INTERVAL = 30  # Check game statuses every 30 seconds


@ray.remote
def ray_start_game(game_id, game_data):
    config = Config()
    game = Game(config, game_id, game_data)
    game.start()
    del game, config
    return game_id  # Return the game_id when complete


def non_ray_start_game(game_id, game_data):
    config = Config()
    game = Game(config, game_id, game_data)
    game.start()
    del game, config
    return game_id


def main(use_ray, max_workers):
    config = Config()
    games = set()  # All games ever seen
    active_games = set()  # Currently active games
    active_games_timestamps = {}  # For timeout detection
    pending_ray_tasks = {}  # For Ray task tracking
    last_status_poll_time = 0  # For status polling interval

    if use_ray:
        ray.init(num_cpus=max_workers)

    while True:
        current_time = time.time()
        game_records = load_games(config.Session, config.IndivGames)

        # SOLUTION 1: Status polling to detect completed games
        if current_time - last_status_poll_time >= STATUS_POLL_INTERVAL:
            print(f'{ins_time()}: Polling for completed games...')

            # Find games marked as completed in the database
            completed_games = {game_id for game_id in active_games
                               if any(g['game_id'] == game_id and g['status'] == 'completed'
                                      for g in game_records)}

            if completed_games:
                print(f'{ins_time()}: Detected completed games: {", ".join(completed_games)}')
                active_games -= completed_games
                # Also remove from timestamps
                for game_id in completed_games:
                    active_games_timestamps.pop(game_id, None)

            last_status_poll_time = current_time

        # SOLUTION 2: Check Ray task completions
        if use_ray and pending_ray_tasks:
            # Check for completed Ray tasks without blocking
            done_refs, _ = ray.wait(list(pending_ray_tasks.keys()), num_returns=len(pending_ray_tasks), timeout=0)
            for ref in done_refs:
                try:
                    completed_game_id = ray.get(ref)  # Get the returned game_id
                    print(f'{ins_time()}: Ray task for game {completed_game_id} completed')
                    active_games.discard(completed_game_id)  # Remove from active games
                    active_games_timestamps.pop(completed_game_id, None)  # Remove from timestamps
                except Exception as e:
                    print(f'{ins_time()}: Error processing Ray task completion: {e}')
                pending_ray_tasks.pop(ref)  # Remove from pending tasks

        # SOLUTION 3: Timeout detection for hung games
        timed_out_games = set()
        for game_id, start_time in list(active_games_timestamps.items()):
            if current_time - start_time > MAX_GAME_DURATION:
                print(f'{ins_time()}: Game {game_id} has exceeded maximum duration and may be hung')
                timed_out_games.add(game_id)
                active_games_timestamps.pop(game_id)

        if timed_out_games:
            active_games -= timed_out_games
            # You might want to update their status in the database as well
            print(f'{ins_time()}: Removed timed out games: {", ".join(timed_out_games)}')

        # Process new games
        game_id_list = [(game['game_id'], game) for game in game_records if game['status'] == 'active']
        game_id_set = set([game_id for game_id, _ in game_id_list])
        new_games = game_id_set - games

        if not new_games:
            print(f'{ins_time()}: No new games detected..')
            time.sleep(5)
        else:
            print(f'{ins_time()}: Active games: {len(active_games)}/{max_workers}')
            for game_id in new_games:
                if len(active_games) >= max_workers:
                    print(
                        f'{ins_time()}: Maximum active games reached. Skipping {game_id} until capacity is released...')
                    continue

                print(f'{ins_time()}: Adding {game_id} to games and commencing routine...')
                games.add(game_id)
                active_games.add(game_id)
                active_games_timestamps[game_id] = current_time  # Record start time

                game_data = next(record for game_id_candidate, record in game_id_list
                                 if game_id_candidate == game_id)

                if use_ray:
                    # Start game with Ray and track the task
                    task_ref = ray_start_game.remote(game_id, game_data)
                    pending_ray_tasks[task_ref] = game_id
                else:
                    # For non-Ray mode, run synchronously and remove immediately after completion
                    try:
                        non_ray_start_game(game_id, game_data)
                        # Game has completed, remove from active tracking
                        active_games.discard(game_id)
                        active_games_timestamps.pop(game_id, None)
                    except Exception as e:
                        print(f'{ins_time()}: Error running game {game_id}: {e}')
                        active_games.discard(game_id)
                        active_games_timestamps.pop(game_id, None)


if __name__ == '__main__':
    main(use_ray=True, max_workers=10)