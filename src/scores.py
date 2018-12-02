import numpy as np
from bayes_opt import BayesianOptimization

from src import config


def calc_accuracy(eval_sims_mat, eval_probes, eval_candidates_mat):  # TODO test
    """
    eval_sims has same shape as eval_candidates_mat (to save memory)
    """
    assert eval_sims_mat.shape == eval_candidates_mat.shape
    num_correct = 0
    for eval_sims_row in eval_sims_mat:
        if np.all(eval_sims_row[1:] < eval_sims_row[0]):  # correct is always in first position
            num_correct += 1
    res = num_correct / len(eval_probes)
    return res


def calc_balanced_accuracy(calc_signals, sims_mean, verbose=True):

    def calc_probes_fs(thr):
        tp, tn, fp, fn = calc_signals(thr)
        precision = np.divide(tp + 1e-10, (tp + fp + 1e-10))
        sensitivity = np.divide(tp + 1e-10, (tp + fn + 1e-10))  # aka recall
        fs = 2 * (precision * sensitivity) / (precision + sensitivity)
        return fs

    def calc_probes_ba(thr):
        tp, tn, fp, fn = calc_signals(thr)
        specificity = np.divide(tn + 1e-10, (tn + fp + 1e-10))
        sensitivity = np.divide(tp + 1e-10, (tp + fn + 1e-10))  # aka recall
        ba = (sensitivity + specificity) / 2  # balanced accuracy
        return ba

    # make thr range
    thr1 = max(0.0, round(min(0.9, round(sims_mean, 2)) - 0.1, 2))  # don't change
    thr2 = round(thr1 + 0.2, 2)
    # use bayes optimization to find best_thr
    if verbose:
        print('Finding best thresholds between {} and {} using bayesian-optimization...'.format(thr1, thr2))
    gp_params = {"alpha": 1e-5, "n_restarts_optimizer": 2}
    if config.Eval.matching_metric == 'fs':
        fun = calc_probes_fs
    elif config.Eval.matching_metric == 'ba':
        fun = calc_probes_ba
    else:
        raise AttributeError('rnnlab: Invalid arg to "metric".')
    bo = BayesianOptimization(fun, {'thr': (thr1, thr2)}, verbose=verbose)
    bo.explore({'thr': [sims_mean]})
    bo.maximize(init_points=2, n_iter=config.Eval.num_opt_steps,
                acq="poi", xi=0.001, **gp_params)  # smaller xi: exploitation
    best_thr = bo.res['max']['max_params']['thr']
    # use best_thr
    results = fun(best_thr)
    res = np.mean(results)
    return res