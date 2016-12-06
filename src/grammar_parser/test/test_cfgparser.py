import unittest
from ..cfgparser import *


class TestOption(unittest.TestCase):
    def test_option_equality(self):
        option_a = Option(lsemantic='"left"', conjs=['left'])
        option_b = Option(lsemantic='"left"', conjs=['left'])

        self.assertEqual(option_a, option_b)

    def test_option_inequality_1(self):
        option_a = Option(lsemantic='"left"', conjs=['left'])
        option_b = Option(lsemantic='"right"', conjs=['right'])

        self.assertNotEqual(option_a, option_b)


class TestConjunct(unittest.TestCase):
    def test_conjunct_equality(self):
        conj_a = Conjunct(name='left', rsemantic='left')
        conj_b = Conjunct(name='left', rsemantic='left')

        self.assertEqual(conj_a, conj_b)


class TestRule(unittest.TestCase):
    def test_rule_equality_1(self):
        rule_a = Rule(lname='SIDE', options=[Option(lsemantic='"left"', conjs=[Conjunct('left')])])
        rule_b = Rule(lname='SIDE', options=[Option(lsemantic='"left"', conjs=[Conjunct('left')])])

        self.assertEqual(rule_a, rule_b)

    def test_from_cfg_def_1(self):
        line = """SIDE["left"] -> left"""
        rule = Rule.from_cfg_def(line)

        self.assertEqual(rule.lname, "SIDE")
        self.assertEqual(len(rule.options), 1)

        expected_option = Option(lsemantic='"left"', conjs=[Conjunct('left')])
        self.assertEqual(rule.options[0], expected_option)

    def test_from_cfg_def_4(self):
        line = """V_GRASP["pick-up"] -> grab | grasp | pick"""

        rule = Rule.from_cfg_def(line)

        grab_rule = Option('"pick-up"', [Conjunct('grab')])
        grasp_rule = Option('"pick-up"', [Conjunct('grasp')])
        pick_up_rule = Option('"pick-up"', [Conjunct('pick')])  # up is missing as well

        self.assertEqual(len(rule.options), 3)

        self.assertIn(grab_rule, rule.options)
        self.assertIn(grasp_rule, rule.options)
        self.assertIn(pick_up_rule, rule.options)


class TestCfgParser(unittest.TestCase):
    def test_add_rule_1(self):
        parser = CFGParser()

        self.assertEqual(len(parser.rules), 0)

        parser.add_rule("""SIDE["left"] -> left""")

        self.assertEqual(len(parser.rules), 1)

        rule = parser.rules["SIDE"]
        self.assertEqual(rule.lname, "SIDE")
        self.assertEqual(len(rule.options), 1)

        expected_option = Option(lsemantic='"left"', conjs=[Conjunct('left')])
        self.assertEqual(rule.options[0], expected_option)

    def test_add_rule_4(self):
        parser = CFGParser()
        parser.add_rule("""V_GRASP["pick-up"] -> grab | grasp | pick""")  # The up after pick is missing to make this work. 'ip' is probably a remaining_str or something

        rule = parser.rules["V_GRASP"]

        grab_rule = Option('"pick-up"', [Conjunct('grab')])
        grasp_rule = Option('"pick-up"', [Conjunct('grasp')])
        pick_up_rule = Option('"pick-up"', [Conjunct('pick')])  # up is missing as well

        self.assertEqual(len(rule.options), 3)

        self.assertIn(grab_rule, rule.options)
        self.assertIn(grasp_rule, rule.options)
        self.assertIn(pick_up_rule, rule.options)


class TestParseNextAtom(unittest.TestCase):
    def test_parse_next_atom_1(self):
        (name, semantics, remaining) = parse_next_atom("""SIDE["left"]""")

        self.assertEqual(name, "SIDE")
        self.assertEqual(semantics, '"left"')
        self.assertEqual(remaining, '')

    def test_parse_next_atom_2(self):
        (name, semantics, remaining) = parse_next_atom("""VP["action": A]""")

        self.assertEqual(name, "VP")
        self.assertEqual(semantics, '"action": A')
        self.assertEqual(remaining, '')

    def test_parse_next_atom_3(self):
        (name, semantics, remaining) = parse_next_atom("""VP["action": "arm-goal", "symbolic": "reset", "side": S]""")

        self.assertEqual(name, "VP")
        self.assertEqual(semantics, '"action": "arm-goal", "symbolic": "reset", "side": S')
        self.assertEqual(remaining, '')


