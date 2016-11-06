# Usage: 
# The path specifies the folder of the project which inside has its releases.
# It takes alphabetically all the releases and uses one for the training set and
# the next one for the test set.
# At the end it computes the mean of AUC and F1 of all the releases
#of this project.

# Get the logistic regression model using the given training data
getModel <- function(trainingData){
  # Build a logistic regression model
  model <- glm(buggy ~ comm+adev+ddev+add+del+own+minor+ data = trainingData , family = binomial(link = "logit"))
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

# Initialize the lists to save the results for each project
aucProjects <- list()
f1Projects <- list()

# path of the folder with the projects
pathProject = "/home/bobim/Documents/TUDelft/msr/R_code/Feature_Vectors/"
project.names <- dir(pathProject)
gini <- list("Camel" = "high", 
             "Isis" = "high", 
             "Wicket" = "high",
             "Hadoop" = "low", 
             "Jackrabbit" = "low",
             "Ofbiz" = "low")

for(j in 1:length(project.names)){
  # Get the path of the project
  path = paste(pathProject, project.names[j],"/", sep="")
  # Get the names of the release files of this project
  # Takes the files in an alphabetically order
  file.names <- dir(path, pattern =".csv")
  aucReleases <- list(c(),c(),c(),c())
  f1Releases <- list(c(),c(),c(),c())
  cat("lol")
  for(i in 2:(length(file.names)-1)){
      release1 <- file.names[i]
      
      for(k in 1:4){
        if(!is.na(file.names[i+k])){
          release2 <- file.names[i+k]
          train <- read.csv(paste(path, release1, sep=""), header=T)
          test <- read.csv(paste(path, release2, sep=""), header=T) 
          # Make the the buggy coulmns binary
          train$buggy = ifelse(train$buggy == "True" & train$bug_discovered_after_next_release == "False", 1, 0);
          test$buggy = ifelse(test$buggy == "True", 1, 0);
          # Build a logistic regression model
          model <- getModel(train)
          # Get the auc and f1 metric of the model applied on the test dataset
          aucF1 = getAucF1(model, test)
          
          cat("PROJECT:",project.names[j],"\n")
          cat("Training:" , release1, "\n","Test:", release2, "\n")
          cat("Auc:", aucF1[[1]], "\n", "F1:", aucF1[[2]], "\n")
          # Save the results
          
          aucReleases[[k]][i-1] = aucF1[1]
          f1Releases[[k]][i-1] = aucF1[2]
        }
      }
  }
  aucProjects[[project.names[j]]] = lapply(aucReleases, function(x) mean(x, na.rm=TRUE))
  f1Projects[[project.names[j]]] = lapply(f1Releases, function(x) mean(x, na.rm=TRUE))
}



# Return the evalution metrics of projects with the given gini label
filterGini <- function(evaluationMetrics, giniLabel) {
  result = list()
  for(j in 1:length(project.names)){
    projectName = project.names[j]
    current = gini[[projectName]]
    if (giniLabel == current){
      result[[projectName]] = unlist(evaluationMetrics[[projectName]])
    }
  }
  return(result)
}
aucLowGiniProjects <- filterGini(aucProjects,"low")
aucHighGiniProjects <- filterGini(aucProjects,"high")
f1LowGiniProjects <- filterGini(f1Projects,"low")
f1HighGiniProjects <- filterGini(f1Projects,"high")

addToDataFrame <- function(evaluationMetrics, dataFrame, giniLabel) {
  names = names(evaluationMetrics)
  result = list(c(),c(),c(),c())
  for(i in 1:length(names)){
    project = evaluationMetrics[[names[i]]]
    cat("project:",project,"\n")
    for(j in 1:length(project)){
      result[[j]][i] = project[j]
    }
  }
  for (i in 1:4){
    dataFrame <- rbind(dataFrame, data.frame(gini=giniLabel, value=unlist(result[[i]]), release=i))
  }
  return(dataFrame)
}
aucDataFrame <- rbind()
aucDataFrame <- addToDataFrame(aucLowGiniProjects, aucDataFrame, "Low Gini")
aucDataFrame <- addToDataFrame(aucHighGiniProjects,aucDataFrame,"High Gini")
aucDataFrame <- subset(aucDataFrame, !is.na(value))
qplot(as.factor(release), data=aucDataFrame, geom="boxplot", y=value, xlab='Release Difference', ylab="AUC",fill=gini) + 
  coord_cartesian(ylim=c(0, 1)) +
 facet_wrap(~gini, scale="free") +
  theme(text=element_text(size=30)) +
  guides(fill=FALSE)

f1DataFrame <- rbind()
f1DataFrame <- addToDataFrame(f1LowGiniProjects, f1DataFrame, "Low Gini")
f1DataFrame <- addToDataFrame(f1HighGiniProjects,f1DataFrame,"High Gini")
f1DataFrame <- subset(f1DataFrame, !is.na(value))
qplot(as.factor(release), data=f1DataFrame, geom="boxplot", y=value, xlab='Release Difference', ylab="F1",fill=gini) + 
  coord_cartesian(ylim=c(0, 1)) +
  facet_wrap(~gini, scale="free") +
  theme(text=element_text(size=30)) +
  guides(fill=FALSE)

#######################################################################################################
# Plot the mean of all projects for low and high gini (box plot)
#######################################################################################################
meanStability <- function(evaluationMetrics) {
  names = names(evaluationMetrics)
  result = list(c(),c(),c(),c())
  for(i in 1:length(names)){
    project = evaluationMetrics[[names[i]]]
    cat("project:",project,"\n")
    for(j in 1:length(project)){
      result[[j]][i] = project[j]
    }
  }
  return(lapply(result, function(x) mean(x, na.rm=TRUE)))
}

meanAucHigh <- meanStability(aucHighGiniProjects)
meanAucLow <- meanStability(aucLowGiniProjects)
meanF1High <- meanStability(f1HighGiniProjects)
meanF1Low <- meanStability(f1LowGiniProjects)

dataFrameAuc <- rbind(data.frame(gini="High Gini", value=unlist(meanAucHigh), release=1:4), 
                      data.frame(gini="Low Gini", value=unlist(meanAucLow), release=1:4))
dataFrameAuc$id = seq.int(nrow(dataFrameAuc))

dataFrameF1 <- rbind(data.frame(gini="High Gini", value=unlist(meanF1High), release=1:4), 
                     data.frame(gini="Low Gini", value=unlist(meanF1Low), release=1:4))
dataFrameF1$id = seq.int(nrow(dataFrameAuc))

qplot(release, data=dataFrameAuc, geom="bar", weight=value, xlab='Release Difference',ylab="AUC",fill=gini) + 
  coord_cartesian(ylim=c(0, 1)) +
  facet_wrap(~gini,scale="free") +
  guides(fill=FALSE)
  
qplot(release, data=dataFrameF1, geom="bar", weight=value, xlab='Release Difference',ylab="F1",fill=gini) + 
  coord_cartesian(ylim=c(0, 1)) + 
  facet_wrap(~gini, scale="free") +
  guides(fill=FALSE)
#######################################################################################################
