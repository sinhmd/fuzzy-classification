#ifndef CPP_RANDOMFUZZYTREE_H
#define CPP_RANDOMFUZZYTREE_H

#include "includes.h"
#include "math_functions.h"
#include "data.h"

struct Node {
    data_t data;
    vector<double> memberships;
    vector<pair<double, double>> ranges;
    function<double(item_t)> f;
    vector<Node *> children;
    double entropy;
    double cardinality;
    map<string, double> weights;

    bool is_leaf() {
        return children.size() == 0;
    }
};

class RandomFuzzyTree {
private:
    Node root;
    int p;
    int feature_n;
    double a_cut;
    double min_gain_threshold;
    map<string, double> w;
    set<int> all_categorical_features;
    set<int> categorical_features_left;
public:
    RandomFuzzyTree() {

    }

    map<string, double> &weights() {
        return w;
    }

    void fit(data_t &data,
             vector<range_t > &ranges,
             vector<int> categorical_features = vector<int>(),
             vector<int> numerical_features = vector<int>(),
             double a_cut = 0.5,
             double min_gain_threshold = 0.000001) {
        root = generate_root_node(data, ranges);
        this->a_cut = a_cut;
        this->feature_n = (int) ranges.size();
        this->p = int(ceil(sqrt(feature_n)));
        this->min_gain_threshold = min_gain_threshold;

        if (categorical_features.size() == 0 and numerical_features.size() == 0) {
            generate_categorical_features(data, categorical_features, numerical_features);
        } else {
            this->all_categorical_features = set<int>(categorical_features.begin(), categorical_features.end());
            this->categorical_features_left = set<int>(categorical_features.begin(), categorical_features.end());
        }

        for (auto &d : data) {
            w[d.second] = 1;
        }

        build_tree();
    }

    bool is_int(double value) {
        return fabs(value - (int) value) < 0.000001;
    }

    void generate_categorical_features(data_t &data, vector<int> &categorical_features, vector<int> &numerical_features) {
        for (int i = 0; i < feature_n; i++) {
            if (find(numerical_features.begin(), numerical_features.end(), i) == numerical_features.end()) {
                if (find(categorical_features.begin(), categorical_features.end(), i) != categorical_features.end()) {
                    this->all_categorical_features.insert(i);
                    this->categorical_features_left.insert(i);
                } else {
                    bool is_categorical = true;
                    set<int> unique_values;
                    for (auto &d : data) {
                        double value = d.first[i];
                        if (!is_int(value)) {
                            is_categorical = false;
                            break;
                        } else {
                            unique_values.insert((int) value);
                        }
                    }

                    if (is_categorical and unique_values.size() < 5) {
                        this->all_categorical_features.insert(i);
                        this->categorical_features_left.insert(i);
                    }
                }
            }
        }
    }

    map<string, double> predict_memberships(item_t &x) {
        map<string, double> memberships_per_class;
        forward_pass(memberships_per_class, root, x, 1);

        return memberships_per_class;
    }

    void forward_pass(map<string, double> &memberships,
                      Node &node,
                      item_t &x,
                      double membership) {
        membership *= node.f(x);

        if (node.is_leaf()) {
            for (auto kv : node.weights) {
                memberships[kv.first] += kv.second * membership;
            }
        } else {
            for (int i = 0; i < node.children.size(); i++) {
                forward_pass(memberships,
                             *node.children[i],
                             x,
                             membership);
            }
        }
    }

    void build_tree() {
        queue<pair<Node *, int> > frontier;
        frontier.push(make_pair(&root, 0));

        while (frontier.size() != 0) {
            pair<Node *, int> curr = (pair<Node *, int> &&) frontier.front();
            Node *node = curr.first;
            int lvl = curr.second;

            vector<Node> children = get_best_children(node);
            if (children.size() != 0) {
                for (int i = 0; i < children.size(); i++) {
                    Node *child = new Node(children[i]);
                    node->children.push_back(child);

                    if (!(feature_n - all_categorical_features.size() == 0 and categorical_features_left.size() == 0)) {
                        frontier.push(make_pair(child, lvl + 1));
                    }
                }
            }

            frontier.pop();
        }
    }

    vector<Node> get_best_children(Node *node) {
        vector<int> features = generate_random_features();
        map<int, vector<Node>> feature_children;
        for (auto f : features) {
            vector<Node> children = generate_feature_best_children(node, f);
            if (are_regular_children(children)) {
                feature_children[f] = children;
            }
        }

        if (feature_children.size() == 0) {
            return vector<Node>();
        } else {
            vector<Node> best_children;
            double best_gain = -1000000;
            for (auto &kv : feature_children) {
                vector<Node> children = kv.second;
                double curr_gain = gain(children, node);
                if (curr_gain > best_gain) {
                    best_children = children;
                    best_gain = curr_gain;
                }
            }

            return best_children;
        }
    }

    bool is_numerical_feature(int feature) {
        return !is_categorical_feature(feature);
    }

    bool is_categorical_feature(int feature) {
        return (all_categorical_features.find(feature) != all_categorical_features.end());
    }

    vector<Node> generate_best_children_categorical_feature(Node *pNode, int feature) {
        if (categorical_features_left.find(feature) != categorical_features_left.end()) {
            set<int> values;
            for (auto &d : pNode->data) {
                values.insert((int &&) d.first[feature]);
            }

            vector<Node> children;
            for (auto v : values) {

                data_t child_data;
                vector<double> child_memberships;
                for (int i = 0; i < pNode->data.size(); i++) {
                    auto d = pNode->data[i];
                    if ((int) d.first[feature] == (int) v) {
                        child_data.push_back(d);
                        child_memberships.push_back(pNode->memberships[i]);
                    }
                }
                Node child;
                child.data = child_data;
                child.ranges = pNode->ranges;
                child.memberships = child_memberships;
                child.cardinality = fuzzy_cardinality(&child);
                child.entropy = fuzzy_entropy(&child);
                child.weights = weights(&child, pNode);
                child.f = [feature, v](pair<vector<double>, string> d) { return (int) d.first[feature] == (int) v; };

                children.push_back(child);
            }

            categorical_features_left.erase(categorical_features_left.find(feature));

            return children;
        } else {
            return vector<Node>();
        }
    }

    vector<Node> generate_feature_best_children(Node *node, int feature) {
        if (is_numerical_feature(feature)) {
            return generate_best_children_numerical_feature(node, feature);
        } else if (is_categorical_feature(feature)) {
            vector<Node> children = generate_best_children_categorical_feature(node, feature);
            return children;
        }
    }

    vector<Node> generate_best_children_numerical_feature(Node *node, int feature) {
        set<double> points;
        for (auto &d : node->data) {
            points.insert(d.first[feature]);
        }

        double lower = node->ranges[feature].first;
        double upper = node->ranges[feature].second;


        double min_el = *min_element(points.begin(), points.end());
        double max_el = *max_element(points.begin(), points.end());
        pair<double, double> search_interval(min_el, max_el);

        map<double, vector<Node>> children_per_point;

        double last_point = -10000;

        random_device rd; // obtain a random number from hardware
        mt19937 eng(rd()); // seed the generator
        uniform_int_distribution<> distr(lower, upper); // define the range

//        int top;
//        int n = 500;
//        if(points.size() < n) {
//            top = (int) points.size();
//        } else {
//            top = n;
//        }
//
//        for(int i = 0; i < top; i++) {
//            double point = distr(eng);
//            if(point > search_interval.first and
//               point < search_interval.second and
//               !eq(point, lower) and
//               !eq(point, upper)) {
//                vector<Node> children =
//                        generate_children_at_point(node, feature, point);
//                children_per_point[point] = children;
//            }
//        }

        for (double point : points) {
            if (point > search_interval.first and point < search_interval.second and !eq(point, lower) and
                !eq(point, upper)) {
                vector<Node> children =
                        generate_children_at_point(node, feature, point);
                if (are_regular_children(children)) {
                    children_per_point[point] = children;
                }
            }
        }

        if (children_per_point.size() == 0) {
            return vector<Node>();
        } else {
            vector<Node> best_children;
            double best_gain = -1000000;
            for (auto &kv : children_per_point) {
                vector<Node> children = kv.second;
                double curr_gain = gain(children, node);
                if (curr_gain > best_gain) {
                    best_children = children;
                    best_gain = curr_gain;
                }
            }

            if (best_gain < min_gain_threshold) {
                return vector<Node>();
            }

            return best_children;
        }
    }

    double gain(vector<Node> &nodes, Node *parent) {
        double gain = parent->entropy;
        for (auto &n : nodes) {
            gain -= (n.cardinality / parent->cardinality) * n.entropy;
        }

        return gain;
    }

    bool are_regular_children(vector<Node> &children) {
        if (children.size() == 0) {
            return false;
        }

        int non_zero_n = 0;
        for (auto &child : children) {
            if (child.data.size() != 0) {
                non_zero_n++;
            }
        }
        return non_zero_n >= 2;
    }

    vector<Node> generate_children_at_point(Node *node, int feature, double point) {
        vector<Node> children;

        double lower = node->ranges[feature].first;
        double upper = node->ranges[feature].second;

        Node left_child;
        left_child.f = triangular(lower, 2 * (point - lower), feature);
        left_child.ranges = node->ranges;
        left_child.ranges[feature].second = point;
        fill_node_properties(node, &left_child);
        children.push_back(left_child);

        Node middle_child;
        middle_child.f = composite_triangular(point,
                                              2 * (point - lower),
                                              2 * (upper - point),
                                              feature);
        middle_child.ranges = node->ranges;
        fill_node_properties(node, &middle_child);
        children.push_back(middle_child);

        Node right_child;
        right_child.f = triangular(upper, 2 * (upper - point), feature);
        right_child.ranges = node->ranges;
        right_child.ranges[feature].first = point;
        fill_node_properties(node, &right_child);
        children.push_back(right_child);

        return children;
    }

    void fill_node_properties(Node *parent, Node *node) {
        node->data = parent->data;

        node->memberships = parent->memberships;
        vector<double> local_memberships = get_local_memberships(node);
        node->memberships = vec_mult(node->memberships, local_memberships);

        vector<item_t > next_data;
        vector<double> next_memberships;

        for (int i = 0; i < node->memberships.size(); i++) {
            if (local_memberships[i] > a_cut) {
                next_data.push_back(node->data[i]);
                next_memberships.push_back(node->memberships[i] *
                                           node->f(node->data[i]));
            }
        }

        node->data = next_data;
        node->memberships = next_memberships;
        node->cardinality = fuzzy_cardinality(node);
        node->entropy = fuzzy_entropy(node);
        node->weights = weights(node, parent);
    }

    map<string, double> weights(Node *node, Node *parent = nullptr) {
        if (node->data.size() != 0) {
            map<string, double> weights_values = {};

            double total = 0;
            for (int i = 0; i < node->data.size(); i++) {
                double val = node->memberships[i];
                weights_values[node->data[i].second] += val;
                total += val;
            }

            for (auto kv : weights_values) {
                weights_values[kv.first] /= total;
            }

            return weights_values;
        } else {
            return map<string, double>();
        }
    }

    double fuzzy_cardinality(Node *node) {
        double cardinality = 0;
        for (auto &val : node->memberships) {
            cardinality += val;
        }

        return cardinality;
    }

    double fuzzy_entropy(Node *node) {
        map<string, double> memberships_per_class;
        for (int i = 0; i < node->data.size(); i++) {
            string cls = node->data[i].second;
            memberships_per_class[cls] += node->memberships[i];
        }

        double entropy = 0;
        for (auto kv : memberships_per_class) {
            double proba = kv.second / node->cardinality;
            if (proba != 0) {
                entropy -= proba * log2(proba);
            }
        }

        return entropy;
    }

    vector<double> vec_mult(vector<double> &a, vector<double> &b) {
        vector<double> res;
        for (int i = 0; i < a.size(); i++) {
            res.push_back(a[i] * b[i]);
        }

        return res;
    }

    vector<double> get_local_memberships(Node *node) {
        vector<double> local_memberships;

        for (auto &d : node->data) {
            double curr_memb = node->f(d);
            local_memberships.push_back(curr_memb);
        }

        return local_memberships;
    }

    vector<int> generate_random_features() {
        vector<int> features;
        for (int i = 0; i < p; i++) {
            int rand_ind = rand();
            int n = feature_n;

            while (rand_ind >= RAND_MAX - (RAND_MAX % n)) {
                rand_ind = rand();
            }
            rand_ind %= n;

            features.push_back(rand_ind);
        }

        return features;
    }

    Node generate_root_node(data_t &data, vector<range_t > &ranges) {
        Node root = Node();
        root.data = data;
        root.ranges = ranges;
        root.memberships = vector<double>(data.size(), 1.0);
        root.f = function<double(item_t)>([](item_t i) { return 1.0; });

        fill_node_properties(&root, &root);

        return root;
    }
};

#endif //CPP_RANDOMFUZZYTREE_H