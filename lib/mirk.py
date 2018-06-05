#!/usr/bin/python

import subprocess
from io import StringIO
import re

import pandas as pd 
import shutil

########################## mirk.py ##########################


VERBOSE = True 

def trace(blabla, lvl = 0): 
	if (VERBOSE):
		print("[mirk.py] " + lvl*"\t" + blabla)

nb_equivalence = {
	"0" : ["(+TRUE - TRUE)", "(-FALSE)"],
	"1" : ["(+TRUE/TRUE)", "(+TRUE*TRUE)", "(-FALSE %in% +TRUE)+TRUE"],
	"2" : ["(+TRUE+TRUE)*(+TRUE)"]
}

def split_str(seq, length):
	return [seq[i:i+length] for i in range(0, len(seq), length)]


def add_eol(Rinput, Routput) : 
	with open(Rinput, 'r') as file :
		filedata = file.read()
	
	replaced = filedata.replace('\n', '#\n').replace('##', '#')
	
	with open(Routput, 'w') as file:
		file.write(replaced)


def add_utils(Rinput, Routput) : 
	with open(Rinput, 'r') as file :
		filedata = file.read()
	
	init_code = """
	
	eval -> eval
	as.raw -> as.raw
	c -> c 
	paste0 -> paste0
	noquote -> noquote
	as.factor -> as.factor
	rawToChar -> rawToChar
	
	nb_to_str = function(num = 0){
	if(num != 0){
		return( paste0(rawToChar(as.raw(c(num %% 256))), nb_to_str(num %/% 256)))
	}else{
		return(rawToChar(as.raw(c(0 %%256 ))))
	}
	}
	
	"""
	replaced = init_code + filedata
			
	with open(Routput, 'w') as file:
		file.write(replaced)
	
		
		
def get_symbol(i = 0): 
	binary = "." + bin(i)[2:]
	return binary.replace("0", ".").replace("1", "_")


def rewrite_code(lexems, outer_scope, init_scope = {}):
	
	code = ""
	scope = init_scope
	#scope = {**outer_scope, **init_scope}
	var_index = 0
	last_symbol_used = None
	block_level = 0
	
	while(len(lexems) > 0 ):
		
		lexem = lexems.pop(0)
		token = lexem[4]
		text = lexem[5]
		
		trace(token + " : " + str(text), 3)
		
		if (token == "COMMENT"):
			code += "\n"
		
		elif (token == "NULL_CONST"):
			code += "NULL"
		
		elif (token == "expr"):
			code += " "
			
		elif (token == "STR_CONST"):
			
			chunks = split_str(text[1:-1], 4)
			code += scope["noquote"] + "(" + scope["paste0"] + "("
			for chunk in chunks :
				codes = [ord(c) for c in chunk]
				num = sum(codes[i] * 256 ** i for i in range(len(codes)))
				code += scope["nb_to_str"] + "(" + str(num) + "),"
			code = code[:-1] # delete last comma
			code += "))"
			#code += str(num)
			#code += text + " "
		
		elif (token == "NUM_CONST"):
			
			#n = float(text)
			#print(n)
			code += text + " "
		
		elif (token == "'$'"):
			#followed by a symbol which is not a true symbol
			lexem_2 = lexems.pop(0)
			token_2 = lexem_2[4]
			text_2 = lexem_2[5]
			
			trace("[Take forward] " + token_2 + " : " + str(text_2), 3)
			
			code += text + text_2 + " "
		
		elif (token == "SYMBOL_FUNCTION_CALL"):
			# if the function is in the scope, replace it
			# otherwise it's in a distant namepace, leave it inplace
			symbol = text
			eq = scope[symbol] if (symbol in scope) else outer_scope[symbol] if (symbol in outer_scope) else symbol
			code += eq
			last_symbol_used = symbol
		
		elif (token == "SYMBOL_FORMALS"):
			# encoutered to bind a symbol in the current scope
			symbol = text
			eq = get_symbol(var_index)
			var_index += 1
			scope[symbol] = eq
			
			code += eq + " "
		
		elif (token == "SYMBOL"):
			
			symbol = text
			
			# we need to look forward if it's for a right assign
			#lexem_2 = next((lexem for lexem in lexems if lexem[4] == "expr"), [0])
			try:
				lexem_2 = lexems[0]
				token_2 = lexem_2[4]
				text_2 = lexem_2[5]
			except Exception as e:
				lexem_2 = None
				token_2 = None
				text_2 = None
			
			
			trace("[Look forward] " + token_2 + " : " + str(text_2), 3)
			
			if(token_2 == "RIGHT_ASSIGN"):
				# in this case we don't lookup , as the first term may be in 
				#another namespace 
				code += symbol + " "
			else:
				# not a right assign, so we know the first part isn't in another namespace
				# is it a known symbol ?
				eq = None 
				if (symbol in scope):
					trace("symbol known in self scope", 3)
					eq = scope[symbol]
				elif (symbol in outer_scope):
					trace("symbol UNknown in self scope but ok in outter scope", 3)
					# warning ! if we found the symbol in the outer_scope but not in the current_scope,
					# there may be a conflict if eq(os) = eq(cs)
					# create an alias 
					eq_out = outer_scope[symbol]
					if (eq_out in scope.values()):
						trace("namespaces conflict", 3)
						# conflict, need to bind it in a new scope var
						eq = get_symbol(var_index)
						var_index += 1
						while(eq in scope.values()):
							eq = get_symbol(var_index)
							var_index += 1
						scope[symbol] = eq
						# need to insert prealable declaration 
						k = code.rfind("\n")
						code = code[:k] + "\n" + eq_out + " -> " + eq + "\n" + code[k+1:]
					else :
						eq = eq_out
				
				if(eq == None): # declare new symbol before use
					eq = get_symbol(var_index)
					var_index += 1
					scope[symbol] = eq
					
				code += eq + " "
				last_symbol_used = symbol
				
		elif(token == "FUNCTION"):
			
			trace("We are going to enter a new function scope", 3)
			inner_scope = {last_symbol_used : scope[last_symbol_used]}
			current_scope = {**outer_scope, **scope} # override outer_scope with scope
			#current_scope = scope
			# prepapre n aliases , with n number of parameters
			i_next_par = 0
			while(lexems[i_next_par][4] != "'{'"):
				i_next_par += 1
			n = [ lex for lex in lexems[:i_next_par] if lex[4] == "SYMBOL_FORMALS" ]
			trace("Look forward : I see " + str(len(n)) + " function args : " + str(n), 4)
			
			# we save the min(local vars, args announced) vars
			for i in range(0, min(len(n), len(current_scope.keys()))):
				current_symbol = get_symbol(i)
				inv_map = {v: k for k, v in current_scope.items()}
				symbol = inv_map[current_symbol]
				trace("Create alias for [" + str(current_symbol) + "] (" + str(symbol) + ")", 4)
				eq = get_symbol(var_index)
				var_index += 1
				inner_scope[symbol] = eq
				k = code.rfind("\n")
				code = code[:k] + "\n" + current_symbol + " -> " + eq + "\n" + code[k+1:]
			
			code += " function"
			
			for i in range(0, len(n)):
				lex = lexems.pop(0)
				code += " " + lex[5] + " "
			
			(subcode, lexems_left) = rewrite_code(lexems, current_scope, inner_scope)
			lexems = lexems_left
			#code += " function" + subcode
			code += subcode
			print()
			print("new scope : ")
			print(current_scope)
		
		elif(token == "'{'"):
			code += "{"
			block_level += 1
		
		elif(token == "'}'"):
			code += "}"
			block_level -= 1
			if (block_level == 0):
				return (code, lexems)
		else:
			code += text
	
	return (code, lexems)

################################################################################
#							MAIN PROCESS 									   #
################################################################################

INPUT = './test/secret.R'
TMP = './test/secret_tmp.R'
OUTPUT = './test/secret_min.R'


trace("# Step 1 : Add some dead code")




trace("# Step 2 : Syntaxic salt")

trace("## Step 2.1 : Utils functions", 1)

add_utils(INPUT, TMP)

trace("## Step 2.2 : Operators overloading", 1)

trace("## Step 2.3 : Weird rewritings", 1)

trace("# Step 3 : Add newlines markers")

add_eol(TMP, TMP)


trace("# Step 4 : Syntaxic Analysis")

cmd = ['Rscript', './lib/syntax_parser.R'] + [TMP]
lexical_analysis = StringIO(subprocess.check_output(cmd, universal_newlines=True))

df = pd.read_csv(lexical_analysis, sep=',')

lexems = [ (row['line1'],  row['col1'],  row['line2'],  row['col2'], row['token'], row['text']) 
			#for index, row in df.iterrows() ]
			for index, row in df[df['terminal'] == True].iterrows() ]

			
			
			
trace("# Step 5 : Rewrite R code")

code_substitute = rewrite_code(lexems, {}, {})[0]
print(code_substitute)

with open(OUTPUT, 'w') as file:
	file.write(code_substitute)

#fn = [ i for i, lexem in enumerate(lexems) if lexem[4] == 'FUNCTION']
#print(fn)
