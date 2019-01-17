import sys

from src import config
from src.aggregator import Aggregator
from src.architectures import comparator
from src.evaluators.matching import Matching
from src.embedders.base import w2e_to_sims
from src.embedders.rnn import RNNEmbedder
from src.embedders.count import CountEmbedder
from src.embedders.random_control import RandomControlEmbedder
from src.embedders.w2vec import W2VecEmbedder

def aggregation_job(ev_name):
    print('Aggregating runs data for eval={}..'.format(ev_name))
    ag_matching = Aggregator(ev_name)
    df = ag_matching.make_df()
    p = config.Dirs.remote_root / '{}.csv'.format(ag_matching.ev_name)
    df.to_csv(p)
    print('Done. Saved aggregated data to {}'.format(ev_name, p))
    return df


def embedder_job(param2val):
    """
    Train a single embedder once, and evaluate all novice and expert scores for each task once
    """
    # print params
    print('===================================================')
    for k, v in param2val.items():
        print(k, v)
    # load embedder
    if 'random_type' in param2val:
        embedder = RandomControlEmbedder(param2val)
    elif 'rnn_type' in param2val:
        embedder = RNNEmbedder(param2val)
    elif 'w2vec_type' in param2val:
        embedder = W2VecEmbedder(param2val)
    elif 'count_type' in param2val:
        embedder = CountEmbedder(param2val)
    elif 'glove_type' in param2val:
        raise NotImplementedError
    else:
        raise RuntimeError('Could not infer embedder name from param2val')
    # stage 1
    if not embedder.has_embeddings():  # TODO if embeddings exist, but not eval, mkae sure that ludwigclsuter does not think it is complete- cut param2val file at very end of stage 2 eval
        print('Training...')
        embedder.train()
        embedder.save_w2freq()
        embedder.save_w2e()
    else:
        print('Found embeddings at {}'.format(embedder.location))
        embedder.load_w2e()
    sys.stdout.flush()
    # stage 2
    for architecture in [
        comparator,
        # classifier
    ]:
        for ev in [
            Matching(architecture, 'cohyponyms', 'semantic'),
            Matching(architecture, 'cohyponyms', 'syntactic'),
            Matching(architecture, 'features', 'is'),
            Matching(architecture, 'features', 'has'),
            Matching(architecture, 'nyms', 'syn'),
            Matching(architecture, 'nyms', 'syn', suffix='_jw'),
            Matching(architecture, 'nyms', 'ant'),
            Matching(architecture, 'nyms', 'ant', suffix='_jw'),
            Matching(architecture, 'hypernyms'),
            Matching(architecture, 'events'),

            # Identification(architecture, 'nyms', 'syn', suffix=''),
            # Identification(architecture, 'nyms', 'ant', suffix=''),
        ]:
            if config.Eval.retrain or config.Eval.debug or not embedder.completed_eval(ev):
                if ev.suffix != '':
                    print('WARNING: Using task file suffix "{}".'.format(ev.suffix))
                if not config.Eval.resample:
                    print('WARNING: Not re-sampling data across replications.')
                # make eval data - row_words can contain duplicates
                vocab_sims_mat = w2e_to_sims(embedder.w2e, embedder.vocab, embedder.vocab)
                all_eval_probes, all_eval_candidates_mat = ev.make_all_eval_data(vocab_sims_mat, embedder.vocab)
                ev.row_words, ev.col_words, ev.eval_candidates_mat = ev.downsample(
                    all_eval_probes, all_eval_candidates_mat)
                if config.Eval.verbose:
                    print('Shape of all eval data={}'.format(all_eval_candidates_mat.shape))
                    print('Shape of down-sampled eval data={}'.format(ev.eval_candidates_mat.shape))
                #
                ev.pos_prob = ev.calc_pos_prob()
                # check embeddings for words
                for p in set(ev.row_words + ev.col_words):
                    if p not in embedder.w2e:
                        raise KeyError('"{}" required for evaluation "{}" is not in w2e.'.format(p, ev.name))
                # score
                sims_mat = w2e_to_sims(embedder.w2e, ev.row_words, ev.col_words)  # sims can have duplicate rows
                ev.score_novice(sims_mat)
                ev.train_and_score_expert(embedder)
                # figs
                if config.Eval.save_figs:
                    ev.save_figs(embedder)
            print('-')
    # done - claim param2val to inform ludwigcluster that all evals are completed
    embedder.claim_params()