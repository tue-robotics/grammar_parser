import unittest
from ..cfgparser import *
from ...grammar_parser import cfgparser
import os


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


def normalize_string(text):
    """
    Normalize a multi-line string.

    :param text: Multi-line text string.
    :type  text: str

    :return: Text string containing normalized lines.
    :rtype:  str

    Normalized lines means:
    - Lines have been shifted to the left margin as far as possible.
    - Lines have no trailing whitespace.
    - Text has no leading or trailing empty lines.
    """
    lead_white_pat = re.compile('^( +)[^ ]')
    lines = [line.rstrip() for line in text.split('\n')]

    # Find trailing empty lines.
    last = len(lines) - 1
    while last >= 0 and lines[last] == '':
        last = last - 1
    if last < 0:
        return ""

    # Find leading empty lines.
    first = 0
    while lines[first] == '':
        first = first + 1

    lines = lines[first:last + 1]

    # Strip common whitespace.
    common_length = None
    for line in lines:
        m = lead_white_pat.match(line)
        if m:
            lead_length = len(m.group(1))
            if common_length is None or lead_length < common_length:
                common_length = lead_length

    if common_length > 0:
        for i, line in enumerate(lines):
            if line != '':
                lines[i] = line[common_length:]

    return "\n".join(lines)


class TestSingleRule(unittest.TestCase):
    def setUp(self):
        grammar = normalize_string("""
            T[{"key":"value"}] -> a b c
        """)

        self.target_rule = 'T'
        self.p = CFGParser.fromstring(grammar)

    def test_single1(self):
        with self.assertRaises(ParseError):
            self.p.parse_raw(self.target_rule, '') # Missing first token 'a'.

    def test_single2(self):
        with self.assertRaises(ParseError):
            self.p.parse_raw(self.target_rule, 'a') # Missing second token 'b'.

    def test_single3(self):
        with self.assertRaises(ParseError):
            self.p.parse_raw(self.target_rule, 'b') # Incorrect first token.

    def test_single4(self):
        with self.assertRaises(ParseError):
            self.p.parse_raw(self.target_rule, 'q') # Incorrect first token.

    def test_single5(self):
        with self.assertRaises(ParseError):
            self.p.parse_raw(self.target_rule, 'a b') # Missing third token.

    def test_single6(self):
        with self.assertRaises(ParseError):
            self.p.parse_raw(self.target_rule, 'a b c d') # Too many words.

    def test_single7(self):
        self.assertEquals(self.p.parse_raw(self.target_rule, 'a b c'), {'key': 'value'})


class TestSubrules(unittest.TestCase):
    def setUp(self):
        grammar = normalize_string("""
            T[X] -> A[X] | B[X]
            A["a"] -> p
            B["b"] -> q
        """)

        self.target_rule = 'T'
        self.p = CFGParser.fromstring(grammar)

    def test_sub1(self):
        self.assertEquals(self.p.parse_raw(self.target_rule, 'p'), 'a')

    def test_sub2(self):
        self.assertEquals(self.p.parse_raw(self.target_rule, 'q'), 'b')


class TestEmptySubrules(unittest.TestCase):
    def setUp(self):
        grammar = normalize_string("""
            T[X] -> A[X] | B[X]
            A["a"] -> p D
            B["b"] -> q E
            D -> | r
            E -> r |
        """)

        self.target_rule = 'T'
        self.p = CFGParser.fromstring(grammar)

    def test_empty_subrule1(self):
        self.assertEquals(self.p.parse_raw(self.target_rule, 'p'), 'a') # D reduces to empty.

    def test_empty_subrule2(self):
        self.assertEquals(self.p.parse_raw(self.target_rule, 'q'), 'b') # E reduces to empty.

    def test_empty_subrule3(self):
        self.assertEquals(self.p.parse_raw(self.target_rule, 'p r'), 'a')

    def test_empty_subrule4(self):
        self.assertEquals(self.p.parse_raw(self.target_rule, 'q r'), 'b')

    def test_empty_subrule5(self):
        with self.assertRaises(ParseError):
            self.p.parse_raw(self.target_rule, 'q x') # Incorrect second token.


class TestComplexGrammar(unittest.TestCase):
    def setUp(self):
        self.target_rule = 'T'

        path = os.path.abspath(os.path.join(cfgparser.__file__, "../../../test/eegpsr_grammar.fcfg"))
        print(path)
        self.p = CFGParser.fromfile(path)

    def test_eegpsr_1(self):
        sentence = "answer a question"
        expected = {'actions': [{'action': 'answer-question'}]}

        actual = self.p.parse(self.target_rule, sentence)

        self.assertEquals(expected, actual)

    def test_eegpsr_2(self):
        sentence = "could you please find rein near the living room"
        expected = {'actions': [{'action': 'find', 'entity': {'loc': {'id': {'id': 'livingroom'}}, 'type': 'person'}}]}

        actual = self.p.parse(self.target_rule, sentence)

        self.assertEquals(expected, actual)

    def test_eegpsr_3(self):
        sentence = "robot exit the arena"
        expected = {'actions': [{'action': 'exit'}]}

        actual = self.p.parse(self.target_rule, sentence)

        self.assertEquals(expected, actual)

    def test_eegpsr_4(self):
        sentence = "could you please deliver me the cans"
        expected = {'actions': [{'action': 'bring', 'to': {'special': 'operator'}, 'entity': {'cat': 'cans'}}]}

        actual = self.p.parse(self.target_rule, sentence)

        self.assertEquals(expected, actual)

    def test_eegpsr_5(self):
        # This sentence does not make any common-sense but grammar-wise it does
        sentence = "could you put the coke which is on the living room in the couch reach the living room and answer her question"
        expected = {'actions': [{'action': 'bring', 'to': {'id': 'couch'}}, {'action': 'navigate', 'entity': {'id': {'id': 'livingroom'}}}, {'action': 'answer-question'}]}

        actual = self.p.parse(self.target_rule, sentence)

        self.assertEquals(expected, actual)
