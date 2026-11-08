from detector import make_groups


def evaluation_groups(data, split):
    seed = 23 if split == 'initial' else 1023
    return make_groups(len(data['images']), seed, 128,
                       evaluator_labels=data['labels'])
