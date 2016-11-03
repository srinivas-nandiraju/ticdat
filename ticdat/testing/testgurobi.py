from ticdat import TicDatFactory, Model, utils
from ticdat.model import gurobi
from ticdat.testing.ticdattestutils import dietSolver, fail_to_debugger, nearlySame
import unittest

#@fail_to_debugger
class TestGurobi(unittest.TestCase):
    can_run = False
    def testDiet(self):
        sln, cost = dietSolver("gurobi")
        self.assertTrue(sln)
        self.assertTrue(nearlySame(cost, 11.8289))

_scratchDir = TestGurobi.__name__ + "_scratch"

# Run the tests.
if __name__ == "__main__":
    td = TicDatFactory()
    if utils.stringish(gurobi) :
        print("!!!!!!!!!FAILING GUROBI UNIT TESTS DUE TO FAILURE TO LOAD GUROBI LIBRARIES!!!!!!!!")
    else:
        TestGurobi.can_run = True
    unittest.main()