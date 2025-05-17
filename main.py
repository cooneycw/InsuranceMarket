import time
import ray
from config.config import Config
from src_code.utils.utils import redis_game_start, redis_game_stop, ins_time, pretend_web_input
from src_code.game.start_game import Game
from src_code.models.db_utils import load_games
# ensure setup.py run first if market code has changed


@ray.remote
def ray_start_game(game_id, game_data):
    config = Config()
    game = Game(config, game_id, game_data)
    game.start()
    del game, config


def non_ray_start_game(game_id, game_data):
    config = Config()
    game = Game(config, game_id, game_data)
    game.start()
    del game, config


def main(use_ray, max_workers):
    config = Config()
    games = set()
    active_games = set()

    if use_ray:
        ray.init(num_cpus=max_workers)

    while True:
        game_records = load_games(config.Session, config.IndivGames)
        game_id_list = [(game['game_id'], game) for game in game_records if game['status'] == 'active']
        game_id_set = set([game_id for game_id, _ in game_id_list])
        new_games = game_id_set - games

        if not new_games:
            print(f'{ins_time()}: No new games detected..')
            time.sleep(5)
        else:
            for game_id in new_games:
                if len(active_games) >= max_workers:
                    print(f'{ins_time()}: Maximum active games reached. Skipping {game_id} until capacity is released...')
                    continue

                print(f'{ins_time()}: Adding {game_id} to games and commencing routine...')
                games.add(game_id)
                active_games.add(game_id)

                game_data = next(record for game_id_candidate, record in game_id_list if game_id_candidate == game_id)
                if use_ray:
                    ray_start_game.remote(game_id, game_data)
                else:
                    non_ray_start_game(game_id, game_data)


if __name__ == '__main__':
    main(use_ray=True, max_workers=10)
