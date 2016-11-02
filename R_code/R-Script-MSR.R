# Usage: 
# The path specifies the folder of the project which inside has its releases.
# It takes alphabetically all the releases and uses one for the training set and
# the next one for the test set.
# At the end it computes the mean of AUC and F1 of all the releases
#of this project.

path = "/home/bill/msr/project/"
file.names <- dir(path, pattern =".csv") #Takes the files in an alphabetically order

for(i in 2:length(file.names)-1){
  release1 <- file.names[i]
  release2 <- file.names[i+1]
  
cat("Training:" , release1, "\n","Test:", release2, "\n")

train <- read.csv(paste(path,release1,sep=""),header=T)

test <- read.csv(paste(path,release2,sep=""),header=T) 

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

#compute the coefficients
#coef = summary(model)$coefficients
#coef

aucL[i]<-auc
fL[i]<-F1
}

aucMean = mean(unlist(aucL))
f1Mean = mean(unlist(fL))
aucMean
f1Mean
