import numpy as np
from itertools import chain

from src import config
from src.params import CountParams, RNNParams, Word2VecParams, RandomControlParams
from src.params import make_param2ids
from src.embedders.rnn import RNNEmbedder
from src.embedders.count import CountEmbedder
from src.embedders.random_control import RandomControlEmbedder
from src.embedders.w2vec import W2VecEmbedder

from src.tasks.categorization import Categorization
from src.tasks.nym_matching import NymMatching

from src.utils import w2e_to_sims
from src.utils import w2e_to_embeds


embedders = chain((CountEmbedder(param2ids) for param2ids in make_param2ids(CountParams)),
                  (W2VecEmbedder(param2ids) for param2ids in make_param2ids(Word2VecParams)),
                  (RNNEmbedder(param2ids) for param2ids in make_param2ids(RNNParams)),
                  (RandomControlEmbedder(param2ids) for param2ids in make_param2ids(RandomControlParams)))

tasks = [
    # NymMatching('noun', 'synonym'),
    Categorization('semantic'),
    Categorization('syntactic')
]

# run full experiment
nov2scores = {}  # TODO this needs to be indexed by all params - timestamp?
exp2scores = {}  # TODO this needs to be indexed by all params - timestamp?
for embedder in embedders:
    # embed
    if embedder.has_embeddings() and not config.Embeddings.retrain:
        print('Found {}'.format(embedder.embeddings_fname))
        print('==========================================================================')
        w2e = embedder.load_w2e()
    else:
        print('{}...'.format('Re-training' if config.Embeddings.retrain else 'Training'))
        print('==========================================================================')
        w2e = embedder.train()
        if config.Embeddings.save:
            embedder.save_w2e(w2e)
    # tasks
    for task in tasks:
        print('---------------------------------------------')
        print('Starting task "{}"'.format(task.name))
        print('---------------------------------------------')
        # check embeddings
        for p in set(task.row_words + task.col_words):
            if p not in w2e:
                raise KeyError('"{}" required for task "{}" is not in w2e.'.format(p, task.name))
        # similarities
        embeds = w2e_to_embeds(w2e)
        sims = w2e_to_sims(w2e, task.row_words, task.col_words, config.Embeddings.sim_method)
        print('Shape of similarity matrix: {}'.format(sims.shape))
        # score
        nov2scores[embedder.name] = (task.name, task.score_novice(sims))
        exp2scores[embedder.name] = (task.name, task.train_and_score_expert(w2e, embeds.shape[1]))
        # figs
        task.save_figs(embedder.name)

# TODO save scores to csv
np.save('novice_scores.npy', nov2scores)
np.save('expert_scores.npy', exp2scores)