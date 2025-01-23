import hashlib


def generate_key_value_pairs(strings, num_bytes):
    key_value_pairs = []

    for string in strings:
        hash_value = hashlib.sha256(string.encode()).hexdigest()
        key = hash_value[-num_bytes:]
        key_value_pairs.append((key, string))

    return key_value_pairs


def has_collision(key_value_pairs):
    keys = [pair[0] for pair in key_value_pairs]
    return len(keys) != len(set(keys))


def load_params():
    # read features from file
    with open('./data/features.txt', 'r', encoding='utf-8') as f:
        params = f.readlines()
    params = [p.strip() for p in params]

    # generate key-value pairs
    hash_length = 4
    key_value_pairs = generate_key_value_pairs(params, hash_length)

    # check for collisions, if there are any, double the hash length and try again
    while has_collision(key_value_pairs):
        hash_length *= 2
        key_value_pairs = generate_key_value_pairs(params, hash_length)

    return key_value_pairs
