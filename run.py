import pandas as pd
from itertools import chain

from src import config
from src.params import CountParams, RNNParams, Word2VecParams, RandomControlParams
from src.params import make_param2id
from src.embedders.rnn import RNNEmbedder
from src.embedders.count import CountEmbedder
from src.embedders.random_control import RandomControlEmbedder
from src.embedders.w2vec import W2VecEmbedder

from src.tasks.category_label_detection import CatLabelDetection
from src.tasks.category_member_verification import CatMEmberVer
from src.tasks.nym_detection import NymDetection

from src.utils import w2e_to_sims


embedders = chain(
    (RNNEmbedder(param2id, param2val) for param2id, param2val in make_param2id(RNNParams)),
    (W2VecEmbedder(param2id, param2val) for param2id, param2val in make_param2id(Word2VecParams)),
    (CountEmbedder(param2id, param2val) for param2id, param2val in make_param2id(CountParams)),
    (RandomControlEmbedder(param2id, param2val) for param2id, param2val in make_param2id(RandomControlParams))
)


# a verification task consists of 2 words that either belong together or not.
# a detection task consists of a word and multiple candidate words where only one candidate belongs with test word.

tasks = [
    CatLabelDetection('semantic'),
    # CatLabelDetection('syntactic'),  # TODO what should labels be ?
    NymDetection('antonym'),
    NymDetection('synonym'),
    CatMEmberVer('semantic'),
    CatMEmberVer('syntactic'),
]

# "sports" required for task "semantic_cat_label_ver" is not in w2e.
# "insect" required for task "semantic_cat_label_ver" is not in w2e.
# "clothing" required for task "semantic_cat_label_ver" is not in w2e.
# "household" required for task "semantic_cat_label_ver" is not in w2e.
# "electronics" required for task "semantic_cat_label_ver" is not in w2e.
# "vehicles" required for task "semantic_cat_label_ver" is not in w2e.
# "mammal" required for task "semantic_cat_label_ver" is not in w2e.

# run full experiment
for embedder in embedders:
    # embed
    if config.Embeddings.retrain or not embedder.has_embeddings():
        print('Training runs')
        print('==========================================================================')
        embedder.train()
        if config.Embeddings.save:
            embedder.save_params()
            embedder.save_w2freq()
            embedder.save_w2e()
    else:
        print('Found embeddings at {}'.format(config.Dirs.runs / embedder.time_of_init))
        print('==========================================================================')
        embedder.load_w2e()
    print('Embedding size={}'.format(embedder.w2e_to_embeds(embedder.w2e).shape[1]))
    # tasks
    for task in tasks:
        for rep_id in range(config.Task.num_reps):  # TODO test
            if config.Task.retrain or not embedder.has_task(task, rep_id):
                print('---------------------------------------------')
                print('Starting task "{}"'.format(task.name))
                print('---------------------------------------------')
                # check runs
                for p in set(task.row_words + task.col_words):
                    if p not in embedder.w2e:
                        raise KeyError('"{}" required for task "{}" is not in w2e.'.format(p, task.name))
                # similarities
                sims = w2e_to_sims(embedder.w2e, task.row_words, task.col_words, config.Embeddings.sim_method)
                print('Shape of similarity matrix: {}'.format(sims.shape))
                # score
                task.score_novice(sims)
                task.train_and_score_expert(embedder, rep_id)
                # figs
                if config.Task.save_figs:
                    task.save_figs(embedder)
            else:
                print('---------------------------------------------')
                print('Embedder has task "{}"'.format(task.name))
                print('---------------------------------------------')


# combine scores
scores_list = []
for p in config.Dirs.runs.rglob('scores_0.csv'):
    scores = pd.read_csv(p, header=None, squeeze=True, index_col=0)  # squeezes into series
    scores = scores.groupby(scores.index).max()
    scores.name = p.parent.name
    scores_list.append(scores)
df = pd.concat(scores_list, axis=1)
df.index.name = 'task'
df.to_csv('all_scores.csv')
print(df)