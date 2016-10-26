
#setwd("C:/....................................")
release1 <- "camel-2.12.0.csv"
release2 <- "camel-2.13.0.csv"

# Read training data
train <- read.csv(release1,header=T)
train$file_path = NULL
# Make the the buggy coulmn binary
train$buggy = ifelse(train$buggy == "True",1,0);

# Read test data
test <- read.csv(release2,header=T) 
test$file_path = NULL
# Make the the buggy coulmn binary
test$buggy = ifelse(test$buggy == "True",1,0);

# Build a logistic regression model
model <- glm(buggy ~ line_contributors_total+line_contributors_minor+line_contributors_major+line_contributors_ownership, data = train , family = binomial(link = "logit"))

# Get labels for test data using the LR model
result <- predict(model,newdata=test,type='response')
result_labels <- ifelse(result > 0.5, 1,0)


#view nr of uniques values by:
#table(result_labels), table(test$buggy)


####Evaluation of data

# Calculate the accuracy
accuracy <- mean(result_labels == test$buggy)

# Recall and Precision

#install.packages("caret")
#Reference::  http://stackoverflow.com/questions/8499361/easy-way-of-counting-precision-recall-and-f1-score-in-r
library(caret)
#there was something wrong with the metrics from under here:
#recall <- sensitivity(as.factor(result_labels), as.factor(test$buggy))
#precision <- posPredValue(as.factor(result_labels),as.factor(test$buggy))

#my code for recall-precision:
myrecall=sum(result_labels == test$buggy & test$buggy==1)/(sum(result_labels == test$buggy & test$buggy==1)+ sum(result_labels != test$buggy & test$buggy==0))
myprecision=sum(result_labels == test$buggy & test$buggy==1)/(sum(result_labels == test$buggy & test$buggy==1)+ sum(result_labels != test$buggy & test$buggy==1))
cat("Recall : ",myrecall)
cat("Precision : ",myprecision)

# F1 metric
F1 <- (2 * myprecision * myrecall) / (myprecision + myrecall)
cat("F1 : ",F1)


# Recall-Precision curve             
RP.perf <- performance(pr, "prec", "rec")
plot (RP.perf)

# Install package ROCR by:
# install.packages("ROCR")
library(ROCR)

pr <- prediction(result, test$buggy)
prf <- performance(pr, measure = "tpr", x.measure = "fpr")
# Plot the ROC curve
plot(prf)

# Compute the area under the curve
auc <- performance(pr, measure = "auc")
auc <- auc@y.values[[1]]
auc
