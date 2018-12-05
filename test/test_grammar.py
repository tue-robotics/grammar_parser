#!/usr/bin/env python
from grammar_parser.cfgparser import CFGParser
import argparse
import os


def read_valid_file(p, arg):
    if not os.path.exists(arg):
        p.error("The file %s does not exist!" % arg)
    else:
        return open(arg, 'r').read()

parser = argparse.ArgumentParser()
parser.add_argument("target", type=str)
parser.add_argument("--grammar", type=str)
parser.add_argument("--grammar-file", type=lambda x: read_valid_file(parser, x))
parser.add_argument("--random", action="store_true")
parser.add_argument("--sentence", type=str)
parser.add_argument("--verify", action="store_true")
args = parser.parse_args()

# Verify the specified grammar
if (args.grammar_file and args.grammar) or (args.grammar_file is None and args.grammar is None):
    parser.error("Please specify either a grammar string using --grammar of a grammar file using --grammar-file")

# Verify sentence
if not args.random and not args.sentence:
    parser.error("Specify a sentence via --sentence or use --random")

grammar = args.grammar_file if args.grammar_file else args.grammar

print "Parsing grammar:\n\n{}\n\n".format(grammar)

grammar_parser = CFGParser.fromstring(grammar)

if args.verify:
    grammar_parser.verify()

sentence = args.sentence if args.sentence else grammar_parser.get_random_sentence(args.target)

print "Parsing sentence:\n\n{}\n\n".format(sentence)

result = grammar_parser.parse(args.target, sentence, debug=True)

print "Result:\n\n{}".format(result)
