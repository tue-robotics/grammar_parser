[![Build Status](https://travis-ci.org/tue-robotics/grammar_parser.svg?branch=master)](https://travis-ci.org/tue-robotics/grammar_parser)

# Parser for (Context Free) Grammars

Example grammars:
```
'T -> yes | no'
```
where 'T' is the so-called root of the grammar. Pipe-characters '|' separate the options to choose from at the grammar root, either 'yes' or 'no'. 
Each '... -> ...' is a Rule in the grammar. A Rule is satisfied if the input string is either of the options at the right side of the arrow. 

Another, for taking restaurant orders:
```
O[P] -> ORDER[P] | can i have a ORDER[P] | i would like ORDER[P] | can i get ORDER[P] | could i have ORDER[P] | may i get ORDER[P] | bring me ORDER[P]
ORDER[OO] -> COMBO[OO] | BEVERAGE[OO]
BEVERAGE[{"beverage": B}] -> BEV[B]
BEVERAGE[{"beverage": B}] -> DET BEV[B]
COMBO[{"food1": F1, "food2": F2}] -> FOOD[F1] and FOOD[F2] | FOOD[F1] with FOOD[F2]
COMBO[{"food1": F1, "food2": F2}] -> DET FOOD[F1] and FOOD[F2] | DET FOOD[F1] with FOOD[F2]
COMBO[{"food1": F1, "food2": F2}] -> FOOD[F1] and DET FOOD[F2] | FOOD[F1] with DET FOOD[F2]
COMBO[{"food1": F1, "food2": F2}] -> DET FOOD[F1] and DET FOOD[F2] | DET FOOD[F1] with DET FOOD[F2]
DET -> a | an
BEV['coke'] -> coke[B]
BEV['fanta'] -> fanta[B]
FOOD['pizza'] -> pizza[B]
BEV['steak'] -> steak[B]
```

Here, the root of the grammar is 'O' and it has a *variable* P. This will be 'unified' with the customers selection. 

The capital-writte bits are references to another Rule. 

```O[P]``` refers to ```ORDER[P]``` is several options. 
The Rule that matches this is ```ORDER[OO]```, which in turn refers to ```COMBO[OO] | BEVERAGE[OO]```. 
Note that while ```O[P]``` used ```P``` as the variable name, ```ORDER[OO]``` used ```OO``` as the variable name. This is just like a variable name in a function call, the caller and the callee can use different names for the same bit of data. 

```BEVERAGE[OO]``` refers to the rules 
```
BEVERAGE[{"beverage": B}] -> BEV[B]
BEVERAGE[{"beverage": B}] -> DET BEV[B]
```
Futher down, ```DET -> a | an``` is defined, so one can use 'a' or 'an' (as a DETerminant). 

With or without DET, the BEVERAGE-rules both refer to ```BEV[B]``` which is defined as either 'coke' or 'fanta' due to the two rules 
```
BEV['coke'] -> coke[B]
BEV['fanta'] -> fanta[B]
```

When one of these rules are satisfied/match, the variable ```B``` is unified: the matching text is assigned to it, i.e ```B``` = ```coke```. When going back up the tree, the ```BEVERAGE[{"beverage": B}] -> BEV[B]``` rule puts the value of ```B``` in the dictionary at the "bevarage" key. 
That bubbles further up the tree to assign that dictionary to the variable ```OO``` in ```ORDER[OO]``` and that bubbles it up into ```O[P]```. 

After an input sentence is parsed according to this grammar, the output is the dictionary assigned to ```OO```: 
```python
{"beverage": "coke"}
```
