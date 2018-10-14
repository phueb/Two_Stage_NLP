import sys
from collections import Counter, OrderedDict
import pyprind
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
from sortedcontainers import SortedDict
import spacy
from spacy.tokenizer import Tokenizer
from itertools import islice

from src import config

nlp = spacy.load('en_core_web_sm')


def w2e_to_sims(w2e, row_words, col_words, method):  # TODO test
    x = np.vstack([w2e[w] for w in row_words])
    y = np.vstack([w2e[w] for w in col_words])
    # sim
    if method == 'cosine':
        res = cosine_similarity(x, y)
    else:
        raise NotImplemented  # TODO how to convert euclidian distance to sim measure?
    return np.around(res, config.Embeddings.precision)


def w2e_to_embeds(w2e):
    embeds = []
    for w in w2e.keys():
        embeds.append(w2e[w])
    res = np.vstack(embeds)
    print('Converted w2e to matrix with shape {}'.format(res.shape))
    return res


def matrix_to_w2e(input_matrix, vocab):
    res = SortedDict()
    for n, w in enumerate(vocab):
        res[w] = input_matrix[n]
    assert len(vocab) == len(res) == len(input_matrix)
    return res


def print_matrix(vocab, matrix, precision, row_list=None, column_list=None):
    w2id = {w: i for i, w in enumerate(vocab)}
    if row_list is not None:
        for i in range(len(row_list)):
            if row_list[i] in w2id:
                row_index = w2id[row_list[i]]
                print('{:<15}   '.format(row_list[i]), end='')
                if column_list is not None:
                    for j in range(len(column_list)):
                        if column_list[j] in w2id:
                            column_index = w2id[column_list[j]]
                        print('{val:6.{precision}f}'.format(precision=precision,
                                                            val=matrix[row_index, column_index]), end='')
                    print()
                else:
                    for i in range(len(matrix[:, 0])):
                        print('{:<15}   '.format(vocab[i]), end='')
                        for j in range(len(matrix[i, :])):
                            print('{val:6.{precision}f}'.format(precision=precision, val=matrix[i, j]), end='')
                        print()
    else:
        for i in range(len(matrix[:, 0])):
            print('{:<15}   '.format(vocab[i]), end='')
            for j in range(len(matrix[i, :])):
                print('{val:6.{precision}f}'.format(precision=precision, val=matrix[i, j]), end='')
            print()


def load_corpus_data(num_vocab=config.Corpus.num_vocab):
    docs = []
    w2freq = Counter()
    # tokenize + count.py words
    p = config.Dirs.corpora / '{}.txt'.format(config.Corpus.name)
    with p.open('r') as f:
        texts = f.read().splitlines()  # removes '\n' newline character
    num_texts = len(texts)
    print('\nTokenizing {} docs...'.format(num_texts))
    tokenizer = Tokenizer(nlp.vocab)
    pbar = pyprind.ProgBar(num_texts, stream=sys.stdout)
    for spacy_doc in tokenizer.pipe(texts, batch_size=config.Corpus.spacy_batch_size):  # creates spacy Docs
        doc = [w.text for w in spacy_doc]
        docs.append(doc)
        c = Counter(doc)
        w2freq.update(c)
        pbar.update()
    # vocab
    if num_vocab is None:  # if no vocab specified, use the whole corpus
        num_vocab = len(w2freq) + 1
    print('Creating vocab of size {}...'.format(num_vocab))
    deterministic_w2f = OrderedDict(sorted(w2freq.items(), key=lambda item: (item[1], item[0]), reverse=True))
    vocab = list(islice(deterministic_w2f.keys(), 0, num_vocab - 1))
    vocab.append(config.Corpus.UNK)
    print('Least frequent word occurs {} times'.format(deterministic_w2f[vocab[-2]]))
    assert '\n' not in vocab
    assert len(vocab) == num_vocab
    # insert UNK + make numeric
    print('Mapping words to ids...')
    t2id = {t: i for i, t in enumerate(vocab)}
    numeric_docs = []
    for doc in docs:
        numeric_doc = []

        for n, token in enumerate(doc):
            if token in t2id:
                numeric_doc.append(t2id[token])
            else:
                numeric_doc.append(t2id[config.Corpus.UNK])
        numeric_docs.append(numeric_doc)
    return numeric_docs, vocab, deterministic_w2f