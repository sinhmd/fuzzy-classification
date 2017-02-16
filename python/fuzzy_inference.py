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

logging.basicConfig(level=logging.DEBUG)

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
		# print("Max label for " + str(data[i]) + " is " + max_label('name'))
		# for j in range(len(db[i])):
			# f = db[i][j]
			# print("\t" + str( f('name') ) + " (" + data[i] + ") = " + str( f(data[i]) ) )

	return rule

def rule_str(r):
	r_str = ""
	for i in range(len(r[0])):
		r_str += r[0][i]('name')
	return r_str

def my_classification(rule, examples):
	logging.debug("Getting rule weight for rule " + rule_str(rule))
	positive_sum = 0
	negative_sum = 0
	total_sum = 0
	for e in examples:
		curr_md = matching_degree(e[0], rule)
		logging.debug("\tMatching degree " + str(e[0]) + " -> " + str(e[1]) + "\t\t= \t" + str(curr_md) )
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

	print("")
	logging.debug("\tCoefficient " + str(coefficient) + "\tClassification " + str(classification))
	print("")

	return [coefficient, classification]

def add_classifications(rb_map):
	for r in rb_map:
		rb_map[r].extend(my_classification(rb_map[r][0], rb_map[r][1]))

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
				rb_map[p] = [ 0, r, [e] ]

	rb_map = dict( [ (r, [ rb_map[r][1], rb_map[r][2] ]) for r in rb_map if rb_map[r][0] != 0 ] )
	add_classifications(rb_map)

	return rb_map

def get_possible_labels(val, range, label_cnt):
	val = float(val)
	L = range[1] - range[0]
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
			max_classification = rb[r][3]

	return max_classification

def example_from_line(line, attribute_indices, class_index, symbol):
	parts = line.split(symbol)

	classification = parts[ class_index ]
	parts = [ parts[i].strip() for i in attribute_indices ]

	example = [parts, classification]

	return example

def load_csv_data(file_name, attribute_indices, class_index, line_cnt, symbol):
	with open(file_name) as f:
		content = head = [next(f) for x in range(line_cnt)]
		lines = [x.strip() for x in content]
		data = [
			example_from_line(l,attribute_indices, class_index, symbol)
			for l in lines
		]

		return data

def find_ranges(examples, indices, discrete_indices = []):
	ranges = []
	for i in indices:
		ranges.append((
			min([float(e[0][i]) for e in examples]),
			max([float(e[0][i]) for e in examples])
		))

	return ranges

def print_real_rule_weights(rb, examples):


def main():
	logging.info("Loading data...")
	# cols = [0, 4, 5, 9, 10, 12, 13, 14, 15, 16, 17, 18, 19, 22, 23, 24, 25, 26, 27, 28, 29, 
		# 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40]
	cols = [1, 3, 5]
	data = load_csv_data(
		"../data/poker-hand-testing.data", 
		cols,
		10,
		10,
		','
	)
	logging.info("Data loaded")
	# random.shuffle(data)
	data = data[0:10]

	for d in data:
		if d[1] == '4':
			d[1] = '1'
		elif d[1] != '1':
			d[1] = '0'

	validation_data_perc = 0.1
	validation_examples = int(validation_data_perc * len(data))

	training_data = data[:-validation_examples]
	verification_data = data[-validation_examples:]

	logging.info("Generating db...")
	label_cnt = 3
	ranges = find_ranges(data, range(len(cols)))
	ranges = [(1,13) for i in range(3)]

	db = generate_db( ranges , label_cnt)

	[logging.debug( str(d) + "\t" + rule_str( rule(d, db) ) + "\t" + \
		str(generate_possible_rules(d[0], ranges, label_cnt)) ) for d in training_data]

	logging.info("Generating rb...")
	rb = generate_rb(training_data, db, ranges, label_cnt)

	[ print(str(r) + " -> " + rule_str(rb[r][0]) + " " + str(rb[r][1]) + "\n") for r in rb ]

	old_rb = old_generate_rb()
	print_real_rule_weights(rb, examples)

	logging.info("Classifying...")

	with Pool(processes=4) as pool:
		classifications = pool.starmap(classify, [ (v[0], rb, list(ranges), label_cnt) for v in verification_data])

	total = 0
	for i in range(len(verification_data)):
		verification = verification_data[i]
		if classifications[i] == str(verification[1]):
			total += 1

	print( "Accuracy% " + str(100 * total / len(verification_data)) )

	for c in set( [ x[1] for x in verification_data ] ):
		print(
			c + " " + str( len( [x for x in verification_data if x[1] == c] ) )
		)

if __name__ == "__main__":
	main()
