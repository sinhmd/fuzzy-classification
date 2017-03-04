from operator import mul
from functools import reduce
import random
import logging
from collections import defaultdict
from functools import partial
import math
import ann
from itertools import product
from multiprocessing import Pool
import numpy as np
import permutation_ga as pga
import data_loader as dl

logger = logging.getLogger()

ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
formatter = logging.Formatter("\033[92m%(asctime)s %(levelname)s\033[0m\t%(message)s")
ch.setFormatter(formatter)
logger.handlers = []
logger.addHandler(ch)

def triangle(center, width, name, x):
    r = width / 2
    k = 1 / r
    
    left = center - r
    right = center + r

    if x == 'name':
        return name
    else:
        x = float(x)

        if left <= x <= center:
            return k * (x - left) + 0
        elif center <= x <= right:
            return -k * (x - center) + 1
        else:
            return 0

def triangular(center, width, name='x'):
    return partial(triangle, center, width, name)

def labels(rng, label_count):
    L = rng[1] - rng[0]
    w = 2 * L / (label_count - 1)

    if w == 0:
        w = 1 # hacky, because division by zero

    return (
        [triangular( rng[0] + i * w / 2.0, w, str(i) ) for i in range(label_count)]
    )

def generate_db(ranges, label_count):
    return [labels(r, label_count) for r in ranges]

def classification(example):
    return example[1]

def input_data(example):
    return example[0]

def matching_degree(example, x):
    l = [  x[0][i](float(example[i])) for i in range(len(example)) ]
    
    dgr = reduce(mul, l, 1)
    return dgr

def rule(example, db):
    data = input_data(example)
    rw = 0.1
    rule = [[], classification(example), rw]

    for i in range(len(db)):
        max_label = max(db[i], key=lambda x: x(data[i]))
        rule[0].append( max_label )
        for j in range(len(db[i])):
            f = db[i][j]

    return rule

def rule_str(r):
    r_str = ""
    for i in range(len(r[0])):
        r_str += r[0][i]('name')
    return r_str

def my_classification(rule, examples):
    positive_sum = 0
    negative_sum = 0
    total_sum = 0
    for e in examples:
        curr_md = matching_degree(e[0], rule)
        if e[1] == '1':
            positive_sum += curr_md
        elif e[1] == '0':
            negative_sum += curr_md
        total_sum += curr_md

    coefficient = abs(positive_sum - negative_sum) / total_sum

    if positive_sum > negative_sum:
        classification = '1'
    else:
        classification = '0'

    return [coefficient, classification]

def add_classifications(rb_map):
    for r in rb_map:
        rb_map[r].extend(my_classification(rb_map[r][0], rb_map[r][1]))

def rule_from_rule_str(rule_str, db):
    r = [[], 0, 0]
    for i in range(len(rule_str)):
        curr_r = rule_str[i]
        r[0].append( db[i][int(curr_r)] )

    return r

def generate_rb(examples, db, ranges, label_cnt):
    rb_map = {}
    for e in examples:
        r = rule(e, db)
        r_str = rule_str(r)
        if r_str in rb_map:
            rb_map[r_str][0] = 1
            rb_map[r_str][2].append(e)
        else:
            rb_map[r_str] = [ 1, r, [e] ]

        possible_rules = generate_possible_rules(e[0], ranges, label_cnt)
        for p in possible_rules:
            if p == r_str:
                continue
            
            if p in rb_map:
                rb_map[p][2].append(e)
            else:
                rb_map[p] = [ 0, rule_from_rule_str(p, db), [e] ]

    rb_map = dict( [ (r, [ rb_map[r][1], rb_map[r][2] ]) for r in rb_map if rb_map[r][0] != 0 ] )
    add_classifications(rb_map)

    return rb_map


def get_possible_labels(val, range, label_cnt):
    val = float(val)
    L = range[1] - range[0]
    if L == 0:
        L = 1
    half_cnt = label_cnt - 1
    half_w = L / half_cnt

    ind = int((val - range[0]) / half_w)

    first = ind
    second = ind + 1

    if second >= label_cnt:
        first -= 1
        second -= 1

    return str(first), str(second)

def generate_possible_rules(example, ranges, label_cnt, lvl = 0, curr = ""):
    # example is just list of atttributes here
    if lvl == len(ranges):
        return [curr]
    else:
        first, second = get_possible_labels(example[lvl], ranges[lvl], label_cnt)

        return generate_possible_rules(example, ranges, label_cnt, lvl + 1, curr + first) + \
            generate_possible_rules(example, ranges, label_cnt, lvl + 1, curr + second)

def classify(example, rb, ranges, label_cnt):
    # example is just list of atttributes here
    possible_rules = generate_possible_rules(example, ranges, label_cnt)
    
    max_degree = 0
    max_classification = None
    for r in possible_rules:
        if r not in rb:
            continue
        curr_md = matching_degree(example, rb[r][0]) * rb[r][2]
        if curr_md > max_degree:
            max_degree = curr_md
            float_values = [ float(v) for v in example ]
            max_classification = rb[r][3]

    return max_classification

def get_accuracy(
    data,
    ranges,
    data_items_cnt, 
    validation_data_perc, 
    label_cnt, 
    data_transformation = None
):

    logger.debug("Calculating accuracy...")
    logger.debug("Shuffling data...")
    random.shuffle(data)
    data = data[0:data_items_cnt]

    logger.debug("Transforming data...")
    if(data_transformation != None):
        for i in range(len(data)):
            data[i] = data_transformation(data[i])

    validation_examples = int(validation_data_perc * len(data))

    training_data = data[:-validation_examples]
    verification_data = data[-validation_examples:]

    logger.debug("Generating db...")
    db = generate_db( ranges , label_cnt)

    logger.debug("Generating rb...")
    rb = generate_rb(training_data, db, ranges, label_cnt)

    logger.debug("Classifying...")
    with Pool(processes=4) as pool:
        classifications = pool.starmap(classify, [ (v[0], rb, list(ranges), label_cnt) for v in verification_data])

    total = 0
    for i in range(len(verification_data)):
        verification = verification_data[i]
        if classifications[i] == str(verification[1]):
            total += 1

    accuracy = 100 * total / len(verification_data)
    logger.debug("Accuracy% " + str(accuracy))

    logger.debug("Class distribution")
    for c in set( [ x[1] for x in verification_data ] ):
        logger.debug(
            "\tData items with class " + c + " -> " + \
                str( len( [x for x in verification_data if x[1] == c] ) )
        )

    return accuracy

if __name__ == "__main__":
    # file_name = "../data/kddcupfull.data"
    # cols = [0, 4, 5, 9, 10, 12, 13, 14 , 15, 16, 17, 18, 19, 22, 23, 24, 25, 26, 27, 28, 29,
    #     30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40]
    # class_col = 41

    file_name = "../data/poker-hand-testing.data"
    cols = range(10)
    class_col = 10

    # file_name = "../data/covtype.data"
    # cols = range(54)
    # class_col = 54

    row_cnt = 1000
    data_items_cnt = 500000
    delimiter_char = ','
    validation_data_perc = 0.1
    label_cnt = 3
    objective_function_data_item_cnt = 10000
    filter_fun = lambda x: x[1] in ['1', '2']

    data_properties = dl.DataProperties(file_name, cols, class_col, row_cnt, filter_fun)
    data_loader = dl.DataLoader(data_properties)
    data_loader.set_logger(logger)
    data_loader.load()

    data = data_and_ranges[0]
    ranges = data_and_ranges[1]

    pga_instance = pga.PermuatationGA(values)

    # logger.info("Feature selection in progress...")
    # objective_function_cache = {}
    # def objective_function(permutation):
    #     my_data_and_ranges = list(
    #         data_and_ranges[0:objective_function_data_item_cnt]
    #     )
            
    #     my_data_and_ranges = (
    #         my_data_and_ranges[0],
    #         [my_data_and_ranges[1][i] for i in permutation]
    #     )

    #     if str(sorted(permutation)) in objective_function_cache:
    #         return objective_function_cache[str(sorted(permutation))]

    #     def data_transformation(d):
    #         d = [ [ d[0][i] for i in permutation ], d[1] ]

    #         if d[1] == '1':
    #             d[1] = '0'
    #         else:
    #             d[1] = '1'

    #         return d

    #     accuracy = get_accuracy(
    #         my_data_and_ranges[0],
    #         my_data_and_ranges[1], 
    #         objective_function_data_item_cnt,
    #         0.1,
    #         3, 
    #         data_transformation
    #     )

    #     objective_function_cache[ str(sorted(permutation)) ] = accuracy

    #     print("Accuracy% ", accuracy)

    #     return accuracy

    # pga_instance.run(objective_function, init_pop_size=10, sample_size=10, generation_cnt=100)
    # best_cols = pga_instance.get_best()

    # logging.info("Recommended features " + str(best_cols))

    # def best_transformation(d):
    #     d = [[d[0][i] for i in best_cols], d[1]]

    #     if d[1] == '1':
    #         d[1] = '0'
    #     else:
    #         d[1] = '1'

    #     return d

    # data_and_ranges = ( data_and_ranges[0],  [data_and_ranges[1][i] for i in best_cols] )

    # logging.info("Classifying dataset " + str(file_name) +  " with " + str(data_items_cnt) + " items...")
    # acc = get_accuracy(
    #     data,
    #     ranges,
    #     data_items_cnt, 
    #     validation_data_perc, 
    #     label_cnt,
    #     best_transformation
    # )
    
    # logging.info("Accuracy% " + str(acc))
