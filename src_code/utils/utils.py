import redis
from datetime import datetime


def pretend_web_input(redis_obj, game_id):
    get_game_list = redis_obj.exists('game_id_list')
    redis_obj.sadd('game_id_list', game_id)


def redis_game_start(redis_obj):
    # return empty set() if there is no key yet
    serv_ready = {
        'key_serv': 'server_ready',
        'key_val': 1,
    }
    server_status_update(redis_obj, serv_ready)
    return init_game_start(redis_obj)


def redis_game_stop(redis_obj):
    serv_ready = {
        'key_serv': 'server_ready',
        'key_val': 0,
    }
    server_status_update(redis_obj, serv_ready)


def init_game_start(redis_obj):
    key_exists = redis_obj.exists('game_id_list')
    if key_exists == 0:
        return set()
    else:
        game_id_bytes = redis_obj.smembers('game_id_list')
        game_id_list = {int(member.decode('utf-8')) for member in game_id_bytes}
        return game_id_list


def server_status_update(redis_obj, serv_ready):
    redis_obj.set(serv_ready['key_serv'], serv_ready['key_val'])


def ins_time():
    current_time = datetime.now()
    formatted_time = current_time.strftime("%Y-%m-%d %H:%M:%S")
    return formatted_time
