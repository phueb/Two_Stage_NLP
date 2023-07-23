import math
import time
import networkx as nx
import numpy as np
from typing import List, Dict, Tuple
from collections import defaultdict

from traindsms.params import CTNParams
from traindsms.dsms.network import NetworkBaseClass


VERBOSE = False
WS = ' '


class CTN(NetworkBaseClass):
    """
    Constituent tree network, generated by joining parsed trees by shared nodes(constituent)

    """

    def __init__(self,
                 params: CTNParams,
                 token2id: Dict[str, int],
                 seq_parsed: List[Tuple],
                 ):
        NetworkBaseClass.__init__(self)

        self.params = params
        self.token2id = token2id
        self.num_vocab = len(token2id)
        self.seq_parsed = seq_parsed

        self.diamond_list = []
        self.lexical_network = None

    def extract_edges_and_nodes(self, x):
        """
        Given a nested list, return the corresponding tree data structure:
        nodes and edges of the tree

        nodes are all constituents in the nested list, and  edges are sub-constituent relations.
        """
        if type(x) == str:
            return [], [x]
        else:
            if type(x) == list:
                x = convert_to_tuple(x)
            edge_set = []
            node_set = []
            for item in x:
                edge_set.append((item, x))
                node_set.append(item)
            if is_not_nested(x):
                return edge_set, node_set
            else:
                for item in x:
                    if type(item) == tuple:
                        tem_tree = self.extract_edges_and_nodes(item)
                        edge_set.extend(tem_tree[0])
                        node_set.extend(tem_tree[1])
                return edge_set, node_set

    def complete_tree(self,
                      x,
                      ):
        """
        get edges and nodes when the tree is just a word.
        """
        edges, nodes = self.extract_edges_and_nodes(x)
        if type(x) == list:
            x = convert_to_tuple(x)
        nodes.append(x)
        return edges, nodes

    def train(self) -> None:
        """
        create the network by joining the trees of the corpus.
        """

        network_edges = []
        network_nodes = []
        for seq_parsed_i in self.seq_parsed:
            edges, nodes = self.complete_tree(seq_parsed_i)

            self.diamond_list.append((edges, nodes))
            network_edges.extend(edges)
            network_nodes.extend(nodes)

        self.node_list = list(set(network_nodes))

        network_edge_dict = {}
        for edge in network_edges:
            if edge in network_edge_dict:
                network_edge_dict[edge] = network_edge_dict[edge] + 1
            else:
                network_edge_dict[edge] = 1

        weighted_network_edge = []
        for edge in network_edge_dict:
            weighted_network_edge.append(edge + (math.log10(network_edge_dict[edge]+1),))

        if VERBOSE:
            print()
            print('Weighted Edges:')
            for edge in weighted_network_edge:
                print(self.node_list.index(edge[0]), self.node_list.index(edge[1]), edge)
            print()

        if VERBOSE:
            print()
            print('Nodes in the network:')
            for node in self.node_list:
                print(self.node_list.index(node), node)

        # make network
        self.network = nx.DiGraph()
        self.network.add_weighted_edges_from(weighted_network_edge)
        self.get_constituent_net()  # this populates self.lexical_network

    def get_neighbor_node(self, node):
        """
        get the neighborhood of a node,
        where a 'neighborhood' refers to all the trees containing the given node.
        """
        neighborhood = [node]
        if self.network.out_degree(node) == 0 or type(self.network.out_degree(node)) != int:
            neighborhood = set(neighborhood)
            return neighborhood
        else:
            count = 1
            while count > 0:
                for n in neighborhood:
                    if self.network.out_degree(n) > 0:
                        for m in self.network.successors(n):
                            neighborhood.append(m)
                            if self.network.out_degree(m) > 0:
                                count = count + 1
                        neighborhood.remove(n)
                        count = count - 1
            real_neighborhood = [1]
            for tree in neighborhood:
                subtree_node = self.complete_tree(tree)[1]
                real_neighborhood.extend(subtree_node)
            real_neighborhood = set(real_neighborhood)
            real_neighborhood.difference_update({1})
            return real_neighborhood

    ###########################################################################################

    # get the 'highest' node, which have 0 out degree (sentence or clause) in the network.

    ###########################################################################################

    # get the constituent distance between linked word pairs (with a edge)

    # for words next to each other in the constituent net, they have an edge if they are at least
    # co-occur in the same tree. Take all trees (sentences) that they co-occur, the constituent
    # distance between word A and B is the average of all distances on the co-occur trees.

    # In a constituent net, the distance between any two words are defined as follow:
    # 1.If they are not connected, then infinity,
    # 2.If they have an edge, defined as above
    # 3.If they are connected, yet there is no edge between, then the distacne is the length of
    # the weighted shortest path between them, where the weight of an edge is the constituent distances
    # between the word pairs linked by the edge.

    def get_constituent_edge_weight(self):

        weight_matrix = np.zeros((self.num_vocab, self.num_vocab), float)
        count_matrix = np.zeros((self.num_vocab, self.num_vocab), float)

        start_time = time.time()
        count = 0
        for tree_info in self.diamond_list:
            sent_node = tree_info[1]
            sent_edge = tree_info[0]
            sent_words = []
            tree = nx.Graph()
            tree.add_edges_from(sent_edge)
            for node in sent_node:
                if type(node) == str:
                    sent_words.append(node)

            for word1 in sent_words:
                for word2 in sent_words:
                    id1 = self.token2id[word1]
                    id2 = self.token2id[word2]
                    if id1 != id2:
                        weight_matrix[id1][id2] = weight_matrix[id1][id2] + .5 ** (
                                nx.shortest_path_length(tree, word1, word2) - 1)
                        # count_matrix[id1][id2] = count_matrix[id1][id2] + 1

            count += 1

        if VERBOSE:
            print(f'Added {count} weights to the weight matrix.')
            print(f'Built weight matrix in {time.time() - start_time} secs.')

        return weight_matrix, count_matrix

    ###########################################################################################

    # create the constituent-net, which is the lexical networks derived from the CTN
    # The nodes of the net are the words in STN, while
    # for constituent-net, 2 words are linked if and only if they co-appear in at least one constituent

    def get_constituent_net(self):
        self.lexical_network = nx.Graph()
        weight_matrix, count_matrix = self.get_constituent_edge_weight()

        weight_normalizer = weight_matrix.sum(0)
        # count_normalizer = count_matrix.sum(0)

        for k in range(self.num_vocab):
            if weight_normalizer[k] == 0:
                # count_normalizer[k] = count_normalizer[k] + 1
                weight_normalizer[k] = weight_normalizer[k] + 1

        for token_i, i in self.token2id.items():
            for token_j, j in self.token2id.items():
                w = weight_matrix[i][j] / (weight_normalizer[i] * weight_normalizer[j]) ** .5
                if w > 0:
                    self.lexical_network.add_edge(token_i, token_j)

    def compute_distance_matrix(self, word_list1, word_list2):  # TODO unused
        """
        for every word pair, compute the constituent distance between
        the lengths of all paths between the word pair
        """
        l1 = len(word_list1)
        l2 = len(word_list2)
        distance_matrix = np.zeros((l1, l2), float)

        count = 0
        epoch = 0
        for i in range(l1):
            for j in range(l2):
                pair = [word_list1[i], word_list2[j]]
                if nx.has_path(self.lexical_network, pair[0], pair[1]):
                    distance = nx.shortest_path_length(self.lexical_network, pair[0], pair[1])
                else:
                    distance = np.inf
                distance_matrix[i][j] = round(distance, 3)

                count = count + 1
                if count >= 5:
                    count = 0
                    epoch = epoch + 5
                    print("{} pairs of distance calculated".format(epoch))

        return distance_matrix

    def compute_similarity_matrix(self,
                                  word_list: List[str],
                                  neighbor_size: int,
                                  ):

        # TODO unused

        graph_list = []
        for word in word_list:
            g = self.get_sized_neighbor(word, neighbor_size)
            graph_list.append(g)
            # print(word, g.nodes)
            # print()

        similarity_matrix = np.zeros((self.num_vocab, self.num_vocab), float)
        for i in range(self.num_vocab):
            for j in range(i, self.num_vocab):
                similarity_matrix[i][j] = round(1 / (1 + nx.graph_edit_distance(graph_list[i], graph_list[j])), 3)
                # print(word_list[i],word_list[j],similarity_matrix[i][j])

        return similarity_matrix

    def calc_sr_scores(self, verb, theme, instruments):

        print(f'Computing relatedness between {verb + WS + theme:>22} and instruments...', flush=True)

        if (verb, theme) in self.node_list:
            sr_verb = self.activation_spreading_analysis(verb, self.node_list,
                                                         excluded_edges=[((verb, theme), theme)])
            sr_theme = self.activation_spreading_analysis(theme, self.node_list,
                                                          excluded_edges=[((verb, theme), verb)])
        else:
            sr_verb = self.activation_spreading_analysis(verb, self.node_list, excluded_edges=[])
            sr_theme = self.activation_spreading_analysis(theme, self.node_list, excluded_edges=[])

        scores = []
        for instrument in instruments:
            sr = math.log(sr_verb[instrument] * sr_theme[instrument])
            if VERBOSE:
                print(f'Relatedness between {verb + WS + theme:>22} and {instrument:>12} is {sr:.4f}', flush=True)
            scores.append(sr)

        return scores

    def get_performance(self):
        return {}


def convert_to_tuple(iterable):
    """
    for a given nested list, return a copy in tuple data type
    """
    if is_not_nested(iterable) == 1:
        return tuple(iterable)
    else:
        return tuple(e if type(e) != iterable else convert_to_tuple(e) for e in iterable)


def is_not_nested(iterable):
    """
    is iterable nested?
    """
    t = 1
    for item in iterable:
        if type(item) == list or type(item) == tuple:
            t = 0
            break
    return True if t == 1 else False
