release1 <- "/home/bobim/Documents/TUDelft/msr/R_code/release-2.4.1.csv"
release2 <- "/home/bobim/Documents/TUDelft/msr/R_code/release-2.5.0.csv"

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
result_labels <- ifelse(result > 0.5, 1, 0)

# Calculate the accuricy
misClasificError <- mean(result_labels != test$buggy)
print(paste('Accuracy',1-misClasificError))

#view nr of uniques values by:
#table(result_labels), table(test$buggy)

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