
library(readr)

args = commandArgs(trailingOnly=TRUE)

code = parse(args[1], keep.source = TRUE)
lex = getParseData(code)
cat(format_csv(lex))
