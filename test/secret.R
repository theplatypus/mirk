# Test script, exposing in a minimal number of lines a few of the R grammar#
# - #

library("dplyr")

# little hack
iris -> iris
rnorm -> rnorm
as.data.frame -> as.data.frame
typeof -> typeof
print -> print 

x = 3
y <- "FOO"
df = as.data.frame(iris)

# function scope in which there is a local
bar = function(x, y = NULL){
	local = rnorm(100)
	df_2 = df %>% filter(df$Sepal.Length <= 6)
	return (df_2$Sepal.Width * x)
}

x = bar(3)
if(typeof(x) == "double"){
	print("Hey !")
}
