# Usage: 
# The path specifies the folder of the project which inside has its releases.
# It takes alphabetically all the releases and uses one for the training set and
# the next one for the test set.
# At the end it computes the mean of AUC and F1 of all the releases
#of this project.

# Get the logistic regression model using the given training data

getModel <- function(trainingData){
  # Build a logistic regression model
  model <- glm(buggy ~  comm + add + adev + own + minor + del  , data = trainingData , family = binomial(link = "logit"))
  return(model)
}

# Return the auc and F1 of the given model used on the test dataset
getAucF1 <- function(model, test){
  # Get labels for test data using the LR model
  result <- predict(model,newdata=test,type='response')
  result_labels <- ifelse(result > 0.5, 1,0)
  
  # Recall and Precision
  myrecall = sum(result_labels == test$buggy & test$buggy==1)/ sum(test$buggy==1)
  myprecision = sum(result_labels == test$buggy & test$buggy==1) / sum(result_labels==1)
  cat("Recall", myrecall, "\n")
  cat("Precision", myprecision, "\n")
  
  # F1 metric
  F1 <- (2 * myprecision * myrecall) / (myprecision + myrecall)
  cat("F1", F1, "\n")
  
  library(ROCR)
  pr <- prediction(result, test$buggy)
  prf <- performance(pr, measure = "tpr", x.measure = "fpr")
  
  auc <- performance(pr, measure = "auc")
  auc <- auc@y.values[[1]]
  return(c(auc,F1))
}

getMeanAndPlot <- function(dataFrame, yaxis, ytitle){
  mean = aggregate(dataFrame[,3], list(projectName=dataFrame$projectName, gini=dataFrame$giniLabel),mean)
  mean$id = seq.int(nrow(mean))
  
  qplot(projectName, data=mean, geom="bar", weight=x, xlab="", ylab=ytitle,fill=projectName) + 
    guides(fill=FALSE) + #guide_legend(title="project")) +
    coord_cartesian(ylim=c(0, yaxis)) +
    facet_wrap(~gini, scale="free") +
    theme(text = element_text(size=30)) +
    theme(axis.text.x=element_text(angle=90))
  
  #return(mean)
}

# Initialize the lists to save the results for each project
aucProjects <- list()
f1Projects <- list()
adevProjects <- list()
commProjects <- list()
addProjects <- list()
delProjects <- list()

coefProjects <- list()

# path of the folder with the projects
pathProject = "/home/bill/msr/Feature_Vectors/"
project.names <- dir(pathProject)
gini <- list("Camel" = "high", "Isis" = "high", "Wicket" = "high", "Hadoop" = "low", "Continuum" = "low","Jackrabbit" = "low", "Ofbiz" = "low")

for(j in 1:length(project.names)){
  # Get the path of the project
  path = paste(pathProject, project.names[j],"/", sep="")
  # Get the names of the release files of this project
  file.names <- dir(path, pattern =".csv") #Takes the files in an alphabetically order
  
  # Initialize the lists to save the results for each release
  aucL <- c()
  fL <- c()
  comm <- c()
  adev <- c()
  add <- c()
  del<- c()
  coefL <- c()
  
  for(i in 2:length(file.names)-1){
    release1 <- file.names[i]
    release2 <- file.names[i+1]
    
    cat("PROJECT:",project.names[j],"\n")
    cat("Training:" , release1, "\n","Test:", release2, "\n")
    
    train <- read.csv(paste(path, release1, sep=""), header=T)
    test <- read.csv(paste(path, release2, sep=""), header=T) 
    
    # Make the the buggy coulmns binary
    train$buggy = ifelse(train$buggy == "True" & train$bug_discovered_after_next_release == "False", 1, 0);
    test$buggy = ifelse(test$buggy == "True", 1, 0);
    
    # Build a logistic regression model
    model <- getModel(train)
    # Get the auc and f1 metric of the model applied on the test dataset
    aucF1 = getAucF1(model, test)
    
    #Save the results
    aucL[i]<-aucF1[1]
    fL[i]<-aucF1[2]
    coefL[i] <- list(summary(model)$coef[, "Pr(>|z|)"])
    
  }
  
  # Save the results of all releases of this project
  aucProjects[[project.names[j]]] <- aucL
  f1Projects[[project.names[j]]] <- fL[!is.na(fL)]
  
  coeffMatrix <- do.call(rbind,coefL)
  coefMeans <- colMeans(coeffMatrix, na.rm = FALSE, dims = 1)
  
  coefProjects[[project.names[j]]] <- coefMeans
  
  cat("PROJECT: ",project.names[j], " has AUC (mean): ", mean(aucProjects[[project.names[j]]])," and", " F1 (mean): ", mean(f1Projects[[project.names[j]]], na.rm = TRUE),"\n")
}

combine <- function(evaluationMetrics) {
  require(plyr)
  result = rbind()
  for(j in 1:length(project.names)){
    projectName = project.names[j]
    giniLabel = gini[[projectName]]
    result <- rbind.fill(result,data.frame(projectName, giniLabel, value=evaluationMetrics[[projectName]]))
  }
  result$id = seq.int(nrow(result))
  return(result)
}
aucDataFrame <- combine(aucProjects)
f1DataFrame <- combine(f1Projects)
coefDataFrame <- do.call(rbind, coefProjects)



library(ggplot2)
### AUC (PER RELEASE)

qplot(id, data=aucDataFrame,geom="bar", weight=value, xlab='', ylab="AUC", fill=projectName) + 
  facet_wrap(~giniLabel, scale = "free") +
  coord_cartesian(ylim=c(0.82, 1.1)) +
  theme(axis.text.x=element_blank()) +
  guides(fill=guide_legend(title="project")) 
  
### F1 (PER RELEASE)

qplot(id, data=f1DataFrame,geom="bar", weight=value, xlab='', ylab="F1", fill=projectName) +
  facet_wrap(~giniLabel, scale = "free") +
  coord_cartesian(ylim=c(0, 0.75)) +
  theme(axis.text.x=element_blank())+
  guides(fill=guide_legend(title="project")) 


###MEAN PLOTS

### AUC AND F1 PER PROJECT
getMeanAndPlot(aucDataFrame, 1, "AUC") #For BarPlot
getMeanAndPlot(f1DataFrame, 0.6, "F1") # For Barplot

#Boxplot AUC (PER PROJECT)
qplot(x=projectName,y=value, xlab="", ylab="AUC",fill=giniLabel,data = aucDataFrame,geom='boxplot') +  
  coord_cartesian(ylim=c(0.25, 1)) +
  facet_wrap(~giniLabel, scale="free") +
  guides(fill=FALSE) +
  theme(text = element_text(size=30)) +
  theme(axis.text.x=element_text(angle=90))

#Boxplot F1 (PER PROJECT)
qplot(x=projectName, y=value, xlab="", ylab="F1", fill=giniLabel, data = f1DataFrame,geom='boxplot') +
  coord_cartesian(ylim=c(0, 0.75)) +
  facet_wrap(~giniLabel, scale = "free") +
  guides(fill=FALSE) +
  theme(text = element_text(size=30)) +
  theme(axis.text.x=element_text(angle=90))
  
### AUC HIGH - LOW GINI BOXPLOT (ALL PROJECTS)
qplot(x=giniLabel,y=value, xlab="", ylab="AUC", fill=giniLabel, data = aucDataFrame, geom='boxplot') +  
  coord_cartesian(ylim=c(0.5, 1)) +
  facet_wrap(~giniLabel, scale="free") +
  guides(fill=FALSE) +
  theme(axis.text.x=element_blank(),text = element_text(size=30))


### F1 HIGH - LOW GINI BOXPLOT (ALL PROJECTS)

qplot(x=giniLabel,y=value, xlab="", ylab="F1", fill=giniLabel, data = f1DataFrame, geom='boxplot') +  
  coord_cartesian(ylim=c(0, 0.7)) +
  facet_wrap(~giniLabel, scale="free") +
  guides(fill=FALSE) +
  theme(axis.text.x=element_blank(),text = element_text(size=30))
