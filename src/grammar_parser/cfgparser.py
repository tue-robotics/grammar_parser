#! /usr/bin/env python
# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------------------------------

"""Grammars for the ContextFreeGrammarParser are built from production rules, corresponding to the Rule-class below.
This means that sentences can be generated (and auto-completed), according to this grammar.
Moreover, sentences can be parsed according to the same rules.

See https://www.tutorialspoint.com/automata_theory/context_free_grammar_introduction.htm and https://en.wikipedia.org/wiki/Context-free_grammar for an introduction to context free grammars.

If there is a rule "A -> one", then that means that to generate something according to rule A, the generated sentence is "one"
In this example "A" is the lname. lname stands for left name, as it's on the left of the arrow.
Sentences are produced and parsed from left to right.

There can be multiple lines in the grammar definition file with the same lname, which simply add ways to produce/parse sentences for that lname.

Rules can refer to each other via their lname.
If a rule A defines a way to start a sentence and refers to B, that means the completion of rule A is one via rule B.
For example, the grammar:
A -> go B
B -> forward
B -> backward
can generate the sentences "go forward" and "go backward". And thus parse these sentences as well.

Rules can also have variables that will be assigned to when a sentence is parsed.
For example, the line:

    VP["action": A] -> V_PLACE[A]

adds a rule for the lname VP, with a field called "action", which will be set to A.
The value for A is determined by a rule with lname V_PLACE, which will determine the value of A.

The rule

    V_PLACE["place"] -> place | put

applies when the text is "place" or "put".
When that is the case, the rule applies and the text "place" is filled in for A.
That means when the text "put" is typed, the variable "action" will be assigned the value "place".

The whole grammar has an entry point, or root rule, from which all the other rules are referred.
Each rule forms branch upon branch, together building a Tree.

When a sentence is parsed, a Tree is built. While this happens, the variables are collected.
When the Tree is completely parsed, the collected variables and their assignments are fetched from the Tree with the get_semantics-method.
This returns a string. However, this string represents a (nested) dictionary that maps a variable to a value.

Semantics describe what a sentence means. In this case, it describes what action to perform and with what to perform it.

The semantics are returned to whomever called CFGParser.parse(...), usually the REPL on console.py.
The REPL sends the semantics to the action_server, which grounds the semantics by implementing the actions.
"""

from __future__ import annotations

from typing import Callable, List, MutableMapping, Optional, Tuple, Union, TYPE_CHECKING

import itertools
import random
import re

if TYPE_CHECKING:
    import graphviz

import rospy
import yaml


class GrammarError(Exception):
    """
    Exception indicating a problem in the grammar rules.
    """

    def __init__(self, message):
        Exception.__init__(self, message)


class ParseError(Exception):
    """
    Exception indicating that the given sentence does not match on the grammar.
    """

    def __init__(self, words: List[str], word_index: int):
        if word_index < 0 or word_index >= len(words):
            msg = f"Word index {word_index} is missing (sentence has {len(words)} words)"
        else:
            msg = f"Word '{words[word_index]}' at index {word_index} failed to match"
        Exception.__init__(self, msg)


class bcolors:
    HEADER = "\033[95m"
    OKBLUE = "\033[94m"
    OKGREEN = "\033[92m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"


class Option:
    """An option is a continuation of a sentence of where there are multiple ways to continue the sentence.
    These choices in an Option are called conjuncts."""

    def __init__(self, lsemantic: str = "", conjs: Optional[List[Conjunct]] = None) -> None:
        """Constructor of an Option
        :param lsemantic the name of the semantics that the option is the continuation of. E.g. if the lsemantic is some action, this option might be the object to perform that action with.
        :param conjs the choices in this option"""
        self.lsemantic = lsemantic
        if conjs is None:
            conjs = []

        self.conjuncts: List[Conjunct] = conjs

    def __repr__(self) -> str:
        return f"Option(lsemantic='{self.lsemantic}', conjs={self.conjuncts})"

    def __eq__(self, other: Option) -> bool:
        if isinstance(other, Option):
            return self.lsemantic == other.lsemantic and self.conjuncts == other.conjuncts

        return False

    @staticmethod
    def from_cfg_def(option_definition: str, left_semantics: str) -> List[Option]:
        """Parse text from the CFG definition into an Option and the choices it is composed of."""
        opt_strs: List[str] = option_definition.split("|")

        for opt_str in opt_strs:  # type: str
            opt_str = opt_str.strip()

            opt = Option(left_semantics)

            while opt_str:
                rname, rsem, opt_str = parse_next_atom(opt_str)
                is_variable = rname[0].isupper()
                opt.conjuncts += [Conjunct(rname, rsem, is_variable)]

            yield opt

    def pretty_print(self, level: int = 0, indent: str = "    ") -> str:
        tabs = level * indent
        ret = "\n"
        ret += tabs + f"Option(lsemantic='{self.lsemantic}', conjs=["
        for conj in self.conjuncts:
            # ret += "\n"
            # ret += tabs + "    " + f"{conj},"
            ret += " "
            ret += conj.pretty_print()
        ret += "])"
        return ret

    def graphviz_id(self) -> str:
        return f"Option '{self.lsemantic}'".replace('"', "").replace(":", "")

    def to_graphviz(self, graph: graphviz.Digraph) -> None:
        for conj in self.conjuncts:
            graph.edge(self.graphviz_id(), conj.graphviz_id())
            conj.to_graphviz(graph)


# ----------------------------------------------------------------------------------------------------


class Conjunct:
    """A Conjunct is a placeholder in the parse-tree, which can be filled in by an Option or a word"""

    def __init__(self, name: str, rsemantic: str = "", is_variable: bool = False):
        """
        :param name: the word or variable
        :param rsemantic: what option is the Conjunct part of
        :param is_variable: is the conjunct variable or terminal?
        """
        self.name: str = name
        self.rsemantic: str = rsemantic
        self.is_variable: bool = is_variable

    def __repr__(self) -> str:
        return f"Conjunct(name='{self.name}', rsemantic='{self.rsemantic}', is_variable={self.is_variable})"

    def __eq__(self, other: Conjunct) -> bool:
        if isinstance(other, Conjunct):
            return (
                self.name == other.name and self.rsemantic == other.rsemantic and self.is_variable == other.is_variable
            )
        return False

    def pretty_print(self, level: int = 0) -> str:
        if self.is_variable or "$" in self.name:
            prefix = self.rsemantic + "="
            return prefix + self.name  # + str(self)
        else:
            return bcolors.OKGREEN + self.name + bcolors.ENDC  # + str(self)

    def graphviz_id(self) -> str:
        return f"Conjunct {self.name}"

    def to_graphviz(self, graph) -> None:
        graph.node(self.graphviz_id())


# ----------------------------------------------------------------------------------------------------


class Rule:
    def __init__(self, lname: str, options: Optional[List[Option]] = None):
        if options is None:
            options = []
        self.lname: str = lname
        self.options: List[Option] = options

    def __repr__(self) -> str:
        return f"Rule(lname='{self.lname}', options={self.options})"

    def __eq__(self, other: Rule) -> bool:
        if isinstance(other, Rule):
            return self.lname == other.lname and self.options == other.options

        return False

    @staticmethod
    def from_cfg_def(s: str) -> Rule:
        tmp = s.split(" -> ")
        if len(tmp) != 2:
            raise Exception("Invalid grammar, please use proper ' -> ' arrows", tmp)

        lname, lsem, outstr = parse_next_atom(tmp[0].strip())

        rule = Rule(lname)

        rule.options = list(Option.from_cfg_def(tmp[1], lsem))

        return rule

    def pretty_print(self, level: int = 0, indent: str = "    ") -> str:
        tabs = level * indent
        ret = ""
        ret += tabs + self.lname
        for option in self.options:
            ret += option.pretty_print(level=level + 1)
        return ret

    def graphviz_id(self) -> str:
        return f"Rule {self.lname}"

    def to_graphviz(self, graph: graphviz.Digraph) -> None:
        for opt in self.options:
            graph.edge(self.graphviz_id(), opt.graphviz_id())
            opt.to_graphviz(graph)


# ----------------------------------------------------------------------------------------------------


class Tree:
    def __init__(self, option: Option):
        self.option: Option = option
        self.subtrees: List[Optional[Tree]] = [None] * len(self.option.conjuncts)
        self.parent: Optional[Tree] = None
        self.parent_tree_idx: int = 0

    def next(self, idx: int) -> Tuple[Optional[Tree], int]:
        if idx + 1 < len(self.option.conjuncts):
            return self, idx + 1
        else:
            if self.parent:
                return self.parent.next(self.parent_tree_idx)
            else:
                return None, 0

    def add_subtree(self, idx: int, tree: Tree) -> Tree:
        tree.parent = self
        tree.parent_tree_idx = idx
        self.subtrees[idx] = tree
        return tree

    def __repr__(self) -> str:
        # TODO: Make this print like a tree
        return str(zip(self.option.conjuncts, self.subtrees))

    def pretty_print(self, level: int = 0, indent: str = "    ") -> str:
        # print self, level
        # tabs = (level-1)*indent + "│   ├───"
        tabs = level * indent + "└───"
        # tabs = "\t" * level #
        ret = ""  # "#tabs + self.option.pretty_print(level=level)
        for conjunct, subtree in zip(self.option.conjuncts, self.subtrees):
            ret += tabs + conjunct.pretty_print() + "\n"
            if hasattr(subtree, "pretty_print"):
                ret += subtree.pretty_print(level=level + 1)
                # ret += "\n"

        return ret


# ----------------------------------------------------------------------------------------------------


def parse_next_atom(s: str) -> Tuple[str, str, str]:
    """
    Returns (name, semantics, remaining_str)
    For example, for "VP[X, Y] foo bar" it returns:

        ("VP", "X, Y", "foo bar")

    :param s:
    :return: Tuple with the rule's lname, the variables involved and the remaining text: ("VP", "X, Y", "foo bar")
    """
    s = s.strip()

    for i in range(0, len(s)):
        c = s[i]
        if c == " ":
            return s[:i], "", s[i:].strip()
        elif c == "[":
            j = s.find("]", i)
            if j < 0:
                raise Exception
            return s[:i], s[i + 1 : j], s[j + 1 :].strip()

    return s, "", ""


# ----------------------------------------------------------------------------------------------------


class CFGParser:
    """
    Parser for parsing the heard sentence, and converting it to information for
    the action that should be performed.

    Usage:
    - For loading a grammar from a file use fromfile().
    - For loading a grammar from a text string use fromstring().

    - For loading a grammar with functions, construct a CFGParser object, add
      the functions using CFGParser.set_function(), and finally load the
      grammar using fromfile or fromstring, passing in the CFGParser object
      as well.

    The parser performs a few basic checks on the grammar, such as missing
    sub-rules and missing functions while loading. The CFGParser.verify function
    goes a step further by expanding all alternatives.

    To parse a sentence, use parse_raw() at a CFGParser instance to get maximum information, or
    use parse() at a CFGParser instance to avoid getting exceptions.
    """

    def __init__(self):
        self.rules: MutableMapping[str, Rule] = {}
        self.functions: MutableMapping[str, Callable] = {}

    @staticmethod
    def fromfile(filename: str, parser: Optional[CFGParser] = None) -> CFGParser:
        """
        Load the grammar from the provided file.

        :param filename: Path to the text file containing the grammar
        :param parser: If not None, the parser to use (else a new parser is created).
        :return: The parser contains the grammar.
        """
        with open(filename) as f:
            s = f.read()
        return CFGParser.fromstring(s, parser)

    @staticmethod
    def fromstring(s: str, parser: Optional[CFGParser] = None) -> CFGParser:
        """
        Load the grammar from the provided text.

        :param s: Text containing the grammar
        :param parser: If not None, the parser to use (else a new parser is created).
        :return: The parser contains the grammar.
        """
        if parser is None:
            parser = CFGParser()

        for line in s.replace(";", "\n").split("\n"):
            line = line.strip()
            if line == "" or line[0] == "#":
                continue
            parser.add_rule(line)

        parser.check_rules()
        return parser

    def check_rules(self) -> None:
        """
        Verify the completeness of the loaded grammar, no rules that refer to missing
        subrules and no functions that don't exist.
        """
        for rule in self.rules.values():
            for option in rule.options:
                for conj in option.conjuncts:
                    if conj.is_variable:
                        assert conj.name in self.rules, f"Rule '{conj.name}' is missing"
                    if conj.name[0] == "$":
                        assert conj.name[1:] in self.functions, f"Function '{conj.name[1:]}' is missing"

    def verify(self, target: Optional[str] = None) -> bool:
        if target is None:
            # Try whether all rules in the grammar are valid
            for r in self.rules:
                self.get_unwrapped(r)
        else:
            self.get_unwrapped(target)

        return True

    def add_rule(self, s: str) -> None:
        rule: Rule = Rule.from_cfg_def(s)

        # See if a rule with this lname already exists. If not, add it
        if rule.lname in self.rules:
            original_rule = self.rules[rule.lname]
            original_rule.options += rule.options
        else:
            self.rules[rule.lname] = rule

    def set_function(self, name: str, func: Callable) -> None:
        """
        Add a new function to the parser. Must be done before loading the grammar.

        TODO #11: Ensure the function expansion result does not refer to missing sub-rules or functions.
        """
        self.functions[name] = func

    def get_semantics(self, tree: Tree) -> str:
        """Get the semantics of a tree.
        This means that variables are unified with their values, which may be recursively gotten from the tree's subtrees.
        """
        semantics = tree.option.lsemantic
        for i in range(0, len(tree.subtrees)):
            conj = tree.option.conjuncts[i]
            subtree = tree.subtrees[i]

            if subtree:
                child_semantics = self.get_semantics(subtree)
                semantics = semantics.replace(conj.rsemantic, child_semantics)

        return semantics

    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -

    def parse(self, target: str, words: Union[str, List[str]], debug=False):
        """
        Parse the given sentence against the grammar loaded in the class. This
        method hides all errors (and returns False in that case). Use the
        self.parse_raw function if the difference between a successful and
        failed parse is relevant.

        :param target: Target rule in the grammar to start parsing the sentence.
        :type target: str.

        :param words: Sentence to parse, either as a single string or a list of words.
        :type words: str, or a list of str.

        :param debug: If True, output the matched sequence in the tree.
        :type debug: Boolean, by default False.

        :return: The captured data value collected during parsing if parsing
                 succeeds, else False.
        """
        try:
            return self.parse_raw(target, words, debug)

        except GrammarError as ex:
            rospy.logerr(f"grammar_parser, Grammar error: {ex}")
            return {}

        except ParseError as ex:
            rospy.logerr(f"grammar_parser, Parse error: {ex}")
            return {}

    def parse_raw(self, target: str, words: Union[str, List[str]], debug: bool = False):
        """
        Parse the given sentence against the grammar loaded in the class. This
        method throws exceptions on failures, the self.parse function returns
        False in such a case.

        :param target: Target rule in the grammar to start parsing the sentence.
        :type target: str.

        :param words: Sentence to parse, either as a single string or a list of words.
        :type words: str, or a list of str.

        :param debug: If True, output the matched sequence in the tree.
        :type debug: Boolean, by default False.

        :return: The captured data value collected during parsing if parsing
                 succeeds, a GrammarError exception if the grammar is found to
                 be incorrect, or a ParseError exception if the sentence fails
                 to match the grammar.
        """
        if isinstance(words, str):
            words = words.split(" ")

        if target not in self.rules:
            raise Exception(f"Target {target} not present in grammar rules")

        rule = self.rules[target]

        best_fail = None
        for opt in rule.options:
            tree = Tree(opt)
            ret = self._parse((tree, 0), words, 0)
            if ret is None:
                if debug:
                    print(tree.pretty_print())
                # Simply take the first tree that successfully parses
                semantics_str = self.get_semantics(tree).replace("<", "[").replace(">", "]")
                semantics: dict = yaml.safe_load(semantics_str)
                # just let the yaml error bubble up, this will give a nice backtrace
                return semantics

            elif best_fail is None or best_fail < ret:
                best_fail = ret

        assert best_fail is not None
        raise ParseError(words, best_fail)

    def _parse(self, tree_idx: Tuple, words: List[str], word_index: int) -> Optional[int]:
        """
        Try to match the provided words on the given grammar rule option.

        :param tree_idx: Tuple of grammar Rule, and rule alternative index.
        :param words: Words to match on the alternative.
        :param word_index: First word in words to match on the alternative.
        :return: On successful match None is returned, else an index in words
                 pointing at the position that failed to match. Note that the
                 index may be equal to the number of words (indicating that
                 words are missing).
        """
        tree, idx = tree_idx

        if not tree:
            # We ran out of grammar.
            if len(words) == word_index:
                # And out of words at the same time, hooray!
                return None
            return word_index

        if len(tree.option.conjuncts) == idx:
            return self._parse(tree.next(idx), words, word_index)

        # At least one grammar symbol exists.
        conj = tree.option.conjuncts[idx]

        if conj.is_variable:
            # Conjunct is a sub-rule, 'check_rules' ensures a sub-rule exists,
            # but functions may introduce new sub-rule calls.
            if conj.name not in self.rules:
                raise GrammarError(f"Rule '{conj.name}' does not exist")

            options = self.rules[conj.name].options

        elif conj.name[0] == "$":
            # Conjunct is a function that must be expanded.
            func_name = conj.name[1:]

            # 'check_rules' ensures the function exists, but a previous
            # $function expansion may be wrong.
            if func_name not in self.functions:
                raise GrammarError(f"Function '{func_name}' does not exist")

            options = self.functions[func_name](words[word_index:])
            # XXX Expanded result should not refer to missing sub-rules or
            # functions. However, any check at this time is too late.

        else:
            # Conjunct is an actual word.
            if word_index >= len(words):
                # Ran out of words but not out of grammar terminals.
                return word_index

            if conj.name == words[word_index]:
                return self._parse(tree.next(idx), words, word_index + 1)
            else:
                return word_index

        best_fail = None
        for opt in options:
            subtree = tree.add_subtree(idx, Tree(opt))
            ret = self._parse((subtree, 0), words, word_index)
            if ret is None:
                return None
            if best_fail is None or best_fail < ret:
                best_fail = ret

        assert best_fail is not None
        return best_fail

    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -

    def next_word(self, target: str, words: List) -> List[str]:
        if target not in self.rules:
            return []

        rule: Rule = self.rules[target]

        next_words: List[str] = []
        for opt in rule.options:
            next_words += self._next_word((Tree(opt), 0), words)

        return next_words

    def _next_word(self, tree_idx: Tuple[Tree, int], words: List[str]) -> List[str]:
        tree, idx = tree_idx

        if not tree:
            return []

        conj = tree.option.conjuncts[idx]

        if conj.is_variable:
            if conj.name not in self.rules:
                return []
            options = self.rules[conj.name].options

        elif conj.name[0] == "$":
            func_name = conj.name[1:]
            if not self.has_completion_function(func_name):
                return []
            options = self.get_completion_function(func_name)(words)

        else:
            if not words:
                return [conj.name]
            elif conj.name == words[0]:
                return self._next_word(tree.next(idx), words[1:])
            else:
                return []

        next_words = []
        for opt in options:
            subtree = tree.add_subtree(idx, Tree(opt))
            next_words += self._next_word((subtree, 0), words)

        return next_words

    def has_completion_function(self, func_name: str) -> bool:
        return func_name in self.functions

    def get_completion_function(self, func_name: str):
        return self.functions[func_name]

    @staticmethod
    def graphviz_id() -> str:
        return "CFGParser"

    def to_graphviz(self, graph) -> None:
        for name, rule in self.rules.items():
            graph.edge(self.graphviz_id(), rule.graphviz_id())
            rule.to_graphviz(graph)

    def visualize_options(
        self, graph: graphviz.Digraph, target_rule: str, previous_words: Optional[List[str]] = None, depth: int = 2
    ) -> None:
        if previous_words is None:
            previous_words = []

        colors = itertools.cycle(["blue", "green", "red", "cyan", "magenta", "black", "purple", "orange"])

        if previous_words:
            previous_word = previous_words[-1]
        else:
            previous_word = target_rule

        graph.node(previous_word)
        next_words = set(self.next_word(target_rule, previous_words))

        if next_words and depth:
            for next_word in next_words:
                graph.edge(previous_word, next_word, color=next(colors))
                self.visualize_options(graph, target_rule, previous_words + [next_word], depth=depth - 1)

    def get_unwrapped(self, lname: str) -> str:
        if lname not in self.rules:
            raise Exception(f"Target {lname} not present in grammar rules")

        rule = self.rules[lname]

        opt_strings = []
        for opt in rule.options:
            conj_strings = []

            for conj in opt.conjuncts:
                if conj.is_variable:
                    unwrapped_string = self.get_unwrapped(conj.name)
                    if unwrapped_string:
                        conj_strings.append(unwrapped_string)
                else:
                    conj_strings.append(conj.name)

            opt_strings.append(" ".join(conj_strings))

        s = "|".join(opt_strings)

        if len(opt_strings) > 1:
            s = "(" + s + ")"

        return s

    def get_random_sentence(self, lname: str) -> str:
        unwrapped = self.get_unwrapped(lname)

        spec = "(%s)" % unwrapped
        while re.search("\([^)]+\)", spec):
            options = re.findall("\([^()]+\)", spec)
            for option in options:
                spec = spec.replace(option, random.choice(option[1:-1].split("|")), 1)

        return spec
