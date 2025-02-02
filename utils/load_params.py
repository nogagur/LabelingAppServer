def load_params():
    """ Loads features from file and assigns simple numeric IDs. """

    # Read features from file
    with open('./data/features.txt', 'r', encoding='utf-8') as f:
        params = [p.strip() for p in f.readlines()]

    # Generate key-value pairs using simple sequential numbers
    key_value_pairs = [(i + 1, param) for i, param in enumerate(params)]

    return key_value_pairs