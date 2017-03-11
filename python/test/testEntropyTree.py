import unittest
from fuzzy_classification.classifiers.EntropyTree \
    import EntropyTree
import numpy as np

class testEntropyTree(unittest.TestCase):
    tree = None

    def setUp(self):
        self.tree = EntropyTree()

    def  test_is_terminal_node_arguments(self):
        data = 1
        with self.assertRaises(ValueError):
            self.tree._is_terminal_node(data)

        data = [1]
        with self.assertRaises(ValueError):
            self.tree._is_terminal_node(data)

        data = [1, 2, 3]
        with self.assertRaises(ValueError):
            self.tree._is_terminal_node(data)
        
        with self.assertRaises(ValueError):
            data = np.array([])
            self.tree._is_terminal_node(data)

        with self.assertRaises(ValueError):
            data = np.array([ [1, 2, 3], [4, 5, 6] ])
            self.tree._is_terminal_node(data)
    
    def test_is_terminal_node(self):
        data = np.array([1, 1, 1, 1, 2, 2, 2, 2, 3, 4])
        self.tree.class_n = 4
        self.assertFalse( self.tree._is_terminal_node(data) )

        data = np.array([1, 1, 2, 2])
        self.tree.class_n = 2
        self.assertFalse( self.tree._is_terminal_node(data) )

        data = np.array([1, 1, 1, 1])
        self.tree.class_n = 2
        self.assertTrue( self.tree._is_terminal_node(data) )

    def test_entropy(self):
        data = np.array([1, 2])
        entropy = self.tree._entropy(data)        
        self.assertAlmostEqual(entropy, 1)

        data = np.array([1, 1])
        entropy = self.tree._entropy(data)        
        self.assertAlmostEqual(entropy, 0)

        data = np.array([1, 1, 1, 1, 2, 2, 2, 2, 3, 4])
        self.tree.class_n = 4
        entropy = self.tree._entropy(data)
        self.assertAlmostEqual(entropy, 1.72, 2)