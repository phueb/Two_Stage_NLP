import argparse

from ludwigcluster.client import Client
from ludwigcluster.config import SFTP
from src import config
from src.params import CountParams, RNNParams, Word2VecParams, RandomControlParams
from src.params import gen_combinations

"""
Do not --skip-data if any code related to corpus has been modified. 
This ensures that no old corpus data is used by workers.
This also requires deleting of any old w2freq or vocab txt files in the corpora folder.
"""

if __name__ == '__main__':
    #
    parser = argparse.ArgumentParser()
    parser.add_argument('-r', '--reps', default=2, action='store', dest='reps', type=int,
                        choices=[1, 2, 3, 4, 5, 6, 7, 8, 9, 10], required=False)
    parser.add_argument('-w', '--worker', default=None, action='store', dest='worker',
                        choices=SFTP.worker_names, required=False)
    parser.add_argument('-s', '--skip_data', default=False, action='store_true', dest='skip_data', required=False)
    parser.add_argument('-t', '--test', action='store_true', dest='test', required=False)
    namespace = parser.parse_args()
    # param2val
    param2val_list = list(gen_combinations(CountParams, namespace.reps)) + \
                     list(gen_combinations(RNNParams, namespace.reps)) + \
                     list(gen_combinations(Word2VecParams, namespace.reps)) + \
                     list(gen_combinations(RandomControlParams, namespace.reps))
    # submit
    data_dirs = ['corpora', 'tasks'] if not namespace.skip_data else []
    client = Client(config.Dirs.runs.parent.name)
    client.submit(src_ps=[config.Dirs.src],
                  data_ps=[config.Dirs.root / d for d in data_dirs],

                  param2val_list=param2val_list,  # TODO test

                  reps=namespace.reps,
                  test=namespace.test,
                  use_log=True,
                  worker=namespace.worker)
