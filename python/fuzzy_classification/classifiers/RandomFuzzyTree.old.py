import numpy as np
from math import log, sqrt, ceil
import random
import string
from copy import copy
import pyximport
from tabulate import tabulate
pyximport.install()
from ..util import math_functions

import matplotlib.pyplot as plt

import textwrap
from textwrap import dedent

from multiprocessing import Pool
from multiprocessing.pool import ThreadPool

from joblib import Parallel, delayed


class FuzzyNode:
    feature = None
    is_terminal=None
    classification=None
    # __slots__ = ['is_terminal',
    #              'classification',
    #              'feature'
    #              'partitioning']


class FuzzyPartitioning:
    def __init__(self):
        self.partitions = []
        self.gain = None
    # __slots__ = ['partitions', 'gain']


class FuzzyPartition:
    __slots__ = ['f', 'node', 'properties', 'ranges']


class FuzzySetProperties:
    __slots__ = ['cardinality',
                 'entropy',
                 'data',
                 'memberships']


# noinspection PyAttributeOutsideInit,PyPropertyAccess,PyUnresolvedReferences
class RandomFuzzyTree:
    def __init__(self,
                 n_jobs=1,
                 p="sqrt",
                 terminal_n_threshold=10,
                 categorical_features=[],
                 a_cut = 0.5,
                 test_generation_file=None,
                 test_indendation_level=1):

        self.test_generation_file = test_generation_file
        self.test_cases_generated = 0
        self.n_jobs = n_jobs
        self.p = p
        self.is_fit = False
        self.terminal_n_threshold = terminal_n_threshold
        self.categorical_features = categorical_features
        self.a_cut = a_cut
        self.test_indentation_level = test_indendation_level

    def fit(self, data, ranges, copy_data=False, classes=(1, 2)):
        self.classes = classes

        if copy_data:
            data = np.copy(data)

        self.ranges = ranges
        self.n_feature = self.count_features(data)

        if self.p == "sqrt":
            self.p = ceil(sqrt(self.n_feature))
        elif self.p == "log":
            self.p = ceil(log(self.n_feature, 2))
        elif self.p == "all":
            self.p = self.n_feature

        tree = self.build_tree(data, np.array([1.0 for d in data]))
        self.root = tree

        self.is_fit = True

    def predict(self, x):
        assert self.is_fit

        memberships = self.predict_memberships(x)
        return max(memberships)

    def predict_memberships(self, x):
        memberships = dict([(c, 0) for c in self.classes])
        self.forward_pass(memberships, x, self.root)

        return memberships

    def score(self, data):
        correct = 0
        for x in data:
            if self.predict(x[:-1]) == x[-1]:
                correct += 1

        return correct / data.shape[0]

    def build_tree(self, data, memberships, lvl=0, ranges=None):
        if ranges == None:
            ranges = self.ranges

        # print("\t\t Bulting tree lvl %d" % (lvl + 1) )
        regular_features = self.get_regular_features(data)

        if len(regular_features) != 0:
            node = self.select_partitioning(data, memberships, regular_features, ranges)
        else:
            node = self.generate_leaf(data, memberships)

        if node.is_terminal or self.is_terminal(node, data, memberships):
            node.is_terminal = True
            node.classification = self.classification(data, memberships)
        else:
            for p in node.partitioning.partitions:
                next_ranges = copy(ranges)
                next_ranges[node.feature] = p.ranges[node.feature]
                p.node = self.build_tree(p.properties.data,
                                         p.properties.memberships,
                                         lvl + 1,
                                         next_ranges)

        return node

    def generate_leaf(self, data, memberships):
        node = FuzzyNode()
        node.is_terminal = True
        node.classification = self.classification(data, memberships)
        return node

    def select_partitioning(self, data, memberships, regular_features, ranges):
        node = FuzzyNode()
        features = np.random.choice(regular_features,
                                    min(self.p, len(regular_features)),
                                    replace=False)
        feature_partitionings = {}
        for feature in features:
            feature_partitionings[feature] = \
                self.best_partitioning(feature, data, memberships, ranges)
        node.feature = max(feature_partitionings,
                           key=lambda x: feature_partitionings[x].gain)
        node.partitioning = feature_partitionings[node.feature]
        node.partitioning.gain = self._fuzzy_entropy(data, memberships)# + node.partitioning.gain
        return node

    def get_regular_features(self, data):
        regular_features = []
        for i in range(len(self.ranges)):
            curr_range = self.ranges[i]
            inds = np.logical_and(data[:, i] != curr_range[0], data[:, i] != curr_range[1]).nonzero()[0]
            if curr_range[0] != curr_range[1] and inds.shape[0] != 0:
                regular_features.append(i)
        return regular_features

    def is_terminal(self, node, data, memberships):
        if memberships.shape[0] == 0:
            return True

        empty_partitions = 0
        for partition in node.partitioning.partitions:
            if partition.properties.memberships.shape[0] <= 1:
                empty_partitions += 1

        if empty_partitions >= 2:
            return True

        data_classes = data[:, -1]
        all_same = True
        for i in range(1, data_classes.shape[0]):
            if int(data_classes[i]) != int(data_classes[0]):
                all_same = False
                break

        if all_same:
            return True

        if abs(node.partitioning.gain) <= 0.000001:
            return True
        else:
            return False

    def forward_pass(self,
                     result_memberships,
                     x,
                     node,
                     membership=1):

        if node.is_terminal:
            for c in self.classes:
                result_memberships[c] += node.classification[c] * membership
        else:
            for partition in node.partitioning.partitions:
                next_membership = membership * partition.f(x[node.feature])
                next_node = partition.node

                self.forward_pass(result_memberships,
                             x,
                             next_node,
                             next_membership)

    @staticmethod
    def count_features(data):
        return data.shape[1] - 1

    def classification(self, data, memberships):
        classification_val = {}
        for c in self.classes:
            inds = (data[:, -1] == c).nonzero()[0]
            classification_val[c] = np.sum(memberships[inds])

        return classification_val

    def best_partitioning(self, feature, data, memberships, ranges):
        if feature in self.categorical_features:
            max_partitioning = FuzzyPartitioning()

            max_category = int(self.ranges[feature][1])
            min_category = int(self.ranges[feature][0])

            for category in range(min_category, max_category + 1):
                partition = FuzzyPartition()
                partition.properties = FuzzySetProperties()

                def f(x):
                    if int(x) == category:
                        return 1
                    else:
                        return 0

                partition.f = f

                inds = (data[:, feature] == category).nonzero()[0]
                partition.properties.data = data[inds, :]
                max_partitioning.partitions.append(partition)

            self.set_properties(max_partitioning.partitions,
                                data,
                                feature,
                                memberships)

            max_partitioning.gain = \
                self.gain(max_partitioning.partitions, memberships)
        else:
            points = np.unique(data[:, feature])
            L, U = self.ranges[feature]

            point_partitionings = {}
            regular_point_occured = False
            last_point = None

            meaningful_length = (U - L) / 10

            for p in points:
                if last_point is None or p - last_point > meaningful_length:
                    if p != L and p != U:
                        curr_partitioning = self.partitioning(data, feature, p, memberships, ranges)
                        if self.count_zero(curr_partitioning) < 2:
                            regular_point_occured = True
                            point_partitionings[p] = \
                                curr_partitioning
                            last_point = p
            if not regular_point_occured:
                midpoint = L + (U - L) / 2
                max_partitioning = self.partitioning(data,
                                                     feature,
                                                     midpoint,
                                                     memberships,
                                                     ranges)
                max_partitioning.midpoint = midpoint
            else:
                max_partitioning_key = max(point_partitionings,
                                           key=lambda x: point_partitionings[x].gain)

                max_partitioning = point_partitionings[max_partitioning_key]
                max_partitioning.midpoint = max_partitioning_key

        self.print_partitioning(max_partitioning, data, feature, ranges)

        return max_partitioning

    def count_zero(self, partitioning):
        cnt = 0
        for part in partitioning.partitions:
            if part.properties.entropy == 0:
               cnt += 1

        return cnt

    def partitioning(self, data, feature, p, memberships, ranges):
        part = FuzzyPartitioning()

        L, U = self.ranges[feature]
        W_left = 2 * (p - L)
        W_middle_left = (p - L)
        W_middle_right = (U - p)
        W_right = 2 * (U - p)

        # TODO: generalize to more
        left_partition = FuzzyPartition()
        left_partition.f = math_functions.triangular(L,
                                                     W_left)
        left_partition.ranges = copy(ranges)
        left_partition.ranges[feature] = L, p
        left_partition.properties = []

        middle_partition = FuzzyPartition()
        middle_partition.f = \
            math_functions.composite_triangular(p,
                                                W_middle_left,
                                                W_middle_right)
        middle_partition.ranges = copy(ranges)
        middle_partition.ranges[feature] = L, U
        middle_partition.properties = []

        right_partition = FuzzyPartition()
        right_partition.f = math_functions.triangular(U,
                                                      W_right)
        right_partition.ranges = copy(ranges)
        right_partition.ranges[feature] = p, U
        right_partition.properties = []

        part.partitions = [left_partition,
                           middle_partition,
                           right_partition]


        self.set_properties(part.partitions, data, feature, memberships)
        part.gain = self.gain(part.partitions, memberships)

        return part

    def print_partitioning(self, partitioning, data, feature, ranges):
        rng = ranges[feature]
        data = data[data[:, feature].argsort()]

        data_table = []
        for d in data:
            data_arr = [d[-1]]
            for partition in partitioning.partitions:
                data_arr.append(round(partition.f(d[feature]), 2))

            data_table.append(data_arr)

        print(tabulate(data_table,
                       headers=['Class', 'First', 'Second', 'Third'],
                       tablefmt='orgtbl'))

        for partition in partitioning.partitions:
            partition_sums = {}
            for d in data:
                for c in self.classes:
                    if d[-1] in partition_sums:
                        if partition.f(d[feature]) >= 0.5:
                            partition_sums[d[-1]] += partition.f(d[feature])
                    else:
                        partition_sums[d[-1]] = 0

            print(partition_sums)

        print("Gain: ", partitioning.gain)

        xs = np.arange(rng[0], rng[1], 0.05).tolist()
        for partition in partitioning.partitions:
            ys = []
            for x in xs:
                ys.append(partition.f(x))

            plt.plot(xs, ys, color="g")

        xs = []
        ys = []
        zs = []
        for d in data:
            xs.append(d[feature])
            ys.append(0.5)
            zs.append(d[-1])

        plt.scatter(xs, ys, c=zs)
        plt.show()

    def set_properties(self, partitions, data, feature, memberships):
        for partition in partitions:

            prop = self._fuzzy_set_properties(data,
                                              feature,
                                              partition,
                                              memberships)
            partition.properties = prop

    def gain(self, partitions, memberships):
        data_cardinality = np.sum(memberships)
        if len(partitions) == 0:
            raise ValueError("Empty partitions")
        properties = [part.properties for part in partitions]
        gain_value = 0
        for prop in properties:
            gain_value -= (prop.cardinality / data_cardinality) * prop.entropy

        return gain_value

    def _fuzzy_set_properties(self, data, feature, partition, memberships):
        if data.shape.__contains__(0):
            raise ValueError("Empty array")

        membership_f = np.vectorize(partition.f)

        data_at_feature = np.copy(data[:, feature])
        set_memberships = membership_f(data_at_feature)

        set_memberships = np.multiply(memberships, set_memberships)

        non_zero_inds = (set_memberships >= self.a_cut).nonzero()[0]
        set_memberships = set_memberships[non_zero_inds]
        set_data = data[non_zero_inds, :]

        cardinality = np.sum(set_memberships)

        entropy = self._fuzzy_entropy(set_data,
                                      set_memberships,
                                      cardinality)

        properties = FuzzySetProperties()
        properties.cardinality = cardinality
        properties.entropy = entropy

        non_zero_inds = (set_memberships >= self.a_cut).nonzero()[0]
        set_data = data[non_zero_inds, :]
        set_memberships = set_memberships[non_zero_inds]

        properties.data = set_data
        properties.memberships = set_memberships

        return properties

    def _fuzzy_entropy(self, data, memberships, cardinality=None):
        if self.should_generate_tests(data):
            self.generate_fuzzy_entropy_test(data,
                                             memberships,
                                             cardinality)

        if data.shape.__contains__(0):
            return 0
            # raise ValueError("Empty array")

        entropy = 0
        if cardinality is None:
            cardinality = np.sum(memberships)

        if cardinality != 0:
            for c in self.classes:
                inds = (data[:, -1] == c).nonzero()[0]
                memberships_at_inds = memberships[inds]
                proba = np.sum(memberships_at_inds) / cardinality
                if proba != 0:
                    entropy -= proba * log(proba, 2)

        return entropy

    def should_generate_tests(self, data):
        return self.test_generation_file is not None and \
               20 < data.shape[0] < 50 and \
               self.test_cases_generated < 3

    def generate_fuzzy_entropy_test(self, data, memberships, cardinality):
        self.test_cases_generated += 1

        test_cases_file = open(self.test_generation_file, "a")

        print("\t\tGenerating tests")
        data = data[:, (-2, -1)].tolist()
        memberships = memberships.tolist()

        indentation = ["    " for i in range(self.test_indentation_level)]
        indentation = "".join(indentation)

        print("", file=test_cases_file)
        test_id = ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(5))

        print("%sdef testFuzzyEntropy_generated_%s(self):" % (indentation, test_id), file=test_cases_file)
        wrapper = textwrap.TextWrapper(initial_indent="%s    " % indentation, width=80,
                                       subsequent_indent=' ' * 24)
        data_str = "data = np.array(%s)" % (data)
        print(wrapper.fill(data_str), file=test_cases_file)

        memberships_str = "memberships= np.array(%s)" % (memberships)

        print(wrapper.fill(memberships_str), file=test_cases_file)
        print("%s    cardinality = %s" % (indentation, cardinality), file=test_cases_file)

        result = "self.tree._fuzzy_entropy(data, memberships, cardinality)"
        print("%s    self.assertAlmostEqual(%s, 0, 2)" % (indentation, result), file=test_cases_file)

        print("", file=test_cases_file)
        test_cases_file.close()

    def __str__(self):
        raise NotImplementedError()
