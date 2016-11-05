# Usage: 
# The path specifies the folder of the project which inside has its releases.
# It takes alphabetically all the releases and uses one for the training set and
# the next one for the test set.
# At the end it computes the mean of AUC and F1 of all the releases
#of this project.

# Get the logistic regression model using the given training data
getModel <- function(trainingData){
  # Build a logistic regression model
  model <- glm(buggy ~ comm + adev + add + del, data = trainingData , family = binomial(link = "logit"))
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
  mean = aggregate(dataFrame[,3], list(projectName=dataFrame$projectName),mean)
  mean$id = seq.int(nrow(mean))
  
  qplot(id, data=mean, geom="bar", weight=x, xlab='', ylab=ytitle,fill=projectName) + 
    guides(fill=guide_legend(title="project")) +
    coord_cartesian(ylim=c(yaxis, 1))
  #return(mean)
}


# Initialize the lists to save the results for each project
aucProjects <- list()
f1Projects <- list()
adevProjects <- list()
commProjects <- list()
addProjects <- list()
delProjects <- list()

# path of the folder with the projects
pathProject = "/home/bill/msr/Feature_Vectors/"
project.names <- dir(pathProject)
gini <- list("Camel" = "high", "Isis" = "high", "Hadoop" = "low", "Continuum" = "low","Jackrabbit" = "low")

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
    
    #save coefficients for each release
    # comm[i] <- summary(model)$coefficients[2,"Pr(>|z|)"]
    # adev[i] <- summary(model)$coefficients[3,"Pr(>|z|)"]
    # add[i] <- summary(model)$coefficients[4,"Pr(>|z|)"]
    # del[i] <- summary(model)$coefficients[5,"Pr(>|z|)"]
  }
  
  # Save the results of all releases of this project
  aucProjects[[project.names[j]]] <- aucL
  f1Projects[[project.names[j]]] <- fL[!is.na(fL)]
  # commProjects[[project.names[j]]] <- comm
  # adevProjects[[project.names[j]]] <- adev
  # addProjects[[project.names[j]]] <- add
  # delProjects[[project.names[j]]] <- del
  
  cat("PROJECT: ",project.names[j], " has AUC (mean): ", mean(aucProjects[[project.names[j]]])," and", " F1 (mean): ", mean(f1Projects[[project.names[j]]], na.rm = TRUE),"\n")
  
}

#result <- data.frame(project.names, unlist(aucProjects), unlist(f1Projects), unlist(commProjects), unlist(addProjects),unlist(adevProjects),unlist(delProjects))

combine <- function(evaluationMetrics) {
  result = rbind()
  for(j in 1:length(project.names)){
    projectName = project.names[j]
    giniLabel = gini[[projectName]]
    result <- rbind(result,data.frame(projectName, giniLabel, value=evaluationMetrics[[projectName]]))
  }
  result$id = seq.int(nrow(result))
  return(result)
}
aucDataFrame <- combine(aucProjects)

library(ggplot2)

qplot(id, data=aucDataFrame,geom="bar", weight=value, xlab='', ylab="AUC", fill=projectName) + coord_cartesian(ylim=c(0.80, 1))

f1DataFrame <- combine(f1Projects)
qplot(id, data=f1DataFrame,geom="bar", weight=value, xlab='', ylab="F1", fill=giniLabel) + coord_cartesian(ylim=c(0, 1))


###MEAN PLOTS

### AUC AND F1 PER PROJECT
getMeanAndPlot(aucDataFrame, 0.8, "AUC") #For BarPlot
getMeanAndPlot(f1DataFrame, 0, "F1") # For Barplot

#Boxplot AUC
qplot(x=projectName,y=value,ylab="AUC",fill=giniLabel,data = aucDataFrame,geom='boxplot') +  
  coord_cartesian(ylim=c(0.85, 1)) +
  facet_wrap(~giniLabel)

#Boxplot F1
qplot(x=projectName, y=value, ylab="F1", fill=giniLabel, data = f1DataFrame,geom='boxplot') +
facet_wrap(~giniLabel)
  


### AUC HIGH - LOW GINI

aucMean = aggregate(aucDataFrame[,3],list(Gini=aucDataFrame$giniLabel),mean)
aucMean$id = seq.int(nrow(aucMean))

qplot(id, data=aucMean, geom="bar", weight=x, xlab='', ylab="AUC",fill=Gini) + 
  guides(fill=guide_legend(title="project")) +
  coord_cartesian(ylim=c(0.85, 1))

f1Mean = aggregate(f1DataFrame[,3],list(Gini=f1DataFrame$giniLabel),mean)
f1Mean$id = seq.int(nrow(f1Mean))

qplot(id, data=f1Mean, geom="bar", weight=x, xlab='', ylab="F1",fill=Gini) + 
  guides(fill=guide_legend(title="project")) +
  coord_cartesian(ylim=c(0, 0.6))

### F1 HIGH - LOW GINI
############################################################################################################
############################################################################################################
############################################################################################################
############################################################################################################
############################################################################################################


############################################################################################################
createFrame <- function(projectName, gini, metricReleases){
  return data.frame(c(projectName), c(gini), mectricReleases))
}
aucProjects[[project.names[3]]]
####HADOOP-F1 score
project = c("hadoop")
f1Plot = c(unlist(f1Hadoop))
f1HadoopFrame = data.frame(project, f1Plot)

###HADOOP-AUC
project = c("hadoop")#,"camel") 
aucPlot = c(unlist(aucHadoop))
aucHadoopFrame = data.frame(project, aucPlot)

###CAMEL-AUC
project = c("camel")
aucPlot = c(unlist(aucCamel))
aucCamelFrame = data.frame(project, aucPlot)

####CAMEL-F1 score
project = c("camel") 
f1Plot = c(unlist(f1Camel))
f1CamelFrame = data.frame(project, f1Plot)


###COMBINED-CAMEL
f1Frame = rbind(f1HadoopFrame, f1CamelFrame)
f1Frame$id=seq.int(nrow(f1Frame))

library(ggplot2)

qplot(id, data=f1Frame,geom="bar", weight=f1Plot,xlab='',ylab="F1",fill=project) #+ coord_cartesian(ylim=c(0.80, 1))


###COMBINED-AUC
aucFrame = rbind(aucHadoopFrame, aucCamelFrame)
aucFrame$id=seq.int(nrow(aucFrame))

qplot(id, data=aucFrame,geom="bar", weight=aucPlot,xlab='',ylab="AUC",fill=project) + coord_cartesian(ylim=c(0.80, 1))


###HADOOP-F1 SCORE
project = c("hadoop")
F1Plot = c(unlist(aucHadoop))
aucHadoopFrame = data.frame(project, aucPlot)


###MEAN PLOTS

###F1 SCORE
qplot(project.names, data=result,geom="bar", weight=unlist.f1Projects.,xlab='',ylab="F1",fill=project.names) + 
  guides(fill=guide_legend(title="project")) +
  coord_cartesian(ylim=c(0, 1))

###AUC
qplot(project.names, data=result,geom="bar", weight=unlist.aucProjects.,xlab='',ylab="AUC",fill=project.names) + guides(fill=guide_legend(title="project"))


