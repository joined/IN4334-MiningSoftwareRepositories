# Usage: 
#   Rscript <file name> <training data> <test data>  > performace.txt
# or Rscript <file name> <data> > performace.txt
#Output example:
#   Accuracy 0.9814781 
#   Recall 0.07142857 
#   Precision 0.2 
#   F1 0.1052632 
#   AUC 0.7074168

args = commandArgs(trailingOnly=TRUE)

if (length(args) == 1){
  train <- read.csv(args[1],header=T)
  test <- read.csv(args[1],header=T)
}

#"/home/bobim/Documents/TUDelft/msr/R_code/release-2.4.1.csv"
#"/home/bobim/Documents/TUDelft/msr/R_code/release-2.5.0.csv"

# Make the the buggy coulmns binary
train$buggy = ifelse(train$buggy == "True" & train$bug_discovered_after_next_release == "False", 1, 0);
test$buggy = ifelse(test$buggy == "True", 1, 0);

# Build a logistic regression model
model <- glm(buggy ~ comm + adev + ddev, data = train , family = binomial(link = "logit"))

# Get labels for test data using the LR model
result <- predict(model,newdata=test,type='response')
result_labels <- ifelse(result > 0.5, 1,0)


#view nr of uniques values by:
#table(result_labels), table(test$buggy)


####Evaluation of data

# Calculate the accuracy
accuracy <- mean(result_labels == test$buggy)
cat("Accuracy", accuracy, "\n")

# Recall and Precision
myrecall = sum(result_labels == test$buggy & test$buggy==1)/ sum(test$buggy==1)
myprecision = sum(result_labels == test$buggy & test$buggy==1) / sum(result_labels==1)

cat("Recall", myrecall, "\n")
cat("Precision", myprecision, "\n")

# F1 metric
F1 <- (2 * myprecision * myrecall) / (myprecision + myrecall)
cat("F1", F1, "\n")


# Install package ROCR by:
# install.packages("ROCR")
library(ROCR)

pr <- prediction(result, test$buggy)
prf <- performance(pr, measure = "tpr", x.measure = "fpr")
# Plot the ROC curve
# plot(prf)

# Compute the area under the curve
auc <- performance(pr, measure = "auc")
auc <- auc@y.values[[1]]
cat("AUC", auc, "\n")