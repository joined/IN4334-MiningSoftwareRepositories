# Usage: 
# The path specifies the folder of the project which inside has its releases.
# It takes alphabetically all the releases and uses one for the training set and
# the next one for the test set.
# At the end it computes the mean of AUC and F1 of all the releases
#of this project.


#
tempor <- data.frame(train=character(),
                 test=character(), 
                 gini=character(),
                 accuracy=double(), 
                 myrecall=double(),
                 myprecision=double(),
                 f1=double(),
                 auc=double(),
                 test=character()) 


aucL <- list()
fL <- list()
comm <- list()
adev <- list()
add <-list()
del<-list()
ddev <- list()
own <- list()
minor <- list()


aucProjects <- list()
f1Projects <- list()
adevProjects <- list()
commProjects <- list()
addProjects <- list()
delProjects <- list()
ddevProjects <- list()
ownProjects <- list()
minorProjects <- list()

#path of the folder with the projects
pathProject = "C:/Users/harri/Desktop/Master/Mining/projects/"
project.names <- dir(pathProject)

path1 = paste(pathProject,project.names[6],"/", sep="")
path2 = paste(pathProject,project.names[3],"/", sep="")


file.names.train <- dir(path1, pattern =".csv") #Takes the files in an alphabetically order
file.names.test <- dir(path2, pattern =".csv") #Takes the files in an alphabetically order

for(i in 1:length(file.names.train)){
  for(j in 1:length(file.names.test)){
  
  release1 <- file.names.train[i]
  release2 <- file.names.test[j]
  
cat("PROJECT:",project.names[j],"\n")
  
cat("Training:" , release1, "\n","Test:", release2, "\n")

train <- read.csv(paste(path1,release1,sep=""),header=T)

test <- read.csv(paste(path2,release2,sep=""),header=T) 

# Make the the buggy coulmns binary
train$buggy = ifelse(train$buggy == "True" & train$bug_discovered_after_next_release == "False", 1, 0);
test$buggy = ifelse(test$buggy == "True", 1, 0);

# Build a logistic regression model
model <- glm(buggy ~ comm + add + del + ddev + adev + own + minor, data = train , family = binomial(link = "logit"))

# Get labels for test data using the LR model
result <- predict(model,newdata=test,type='response')
result_labels <- ifelse(result > 0.5, 1,0)


#view nr of uniques values by:
#table(result_labels), table(test$buggy)


####Evaluation of data

# Calculate the accuracy
accuracy <- mean(result_labels == test$buggy)
#cat("Accuracy", accuracy, "\n")

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

newRow <- data.frame(train=release1,test=release2,accuracy=accuracy,myrecall=myrecall,myprecision=myprecision,f1=F1,auc=auc)

tempor=rbind(tempor,newRow)
}}

camel12 <- data.frame(project="camel",
                     gini="high",
                         accuracy=mean(tempor$accuracy,na.rm = TRUE), 
                         myrecall=mean(tempor$myrecall,na.rm = TRUE),
                         myprecision=mean(tempor$myprecision,na.rm = TRUE),
                         f1=mean(tempor$f1,na.rm = TRUE),
                         auc=mean(tempor$auc,na.rm = TRUE),
                        test="high") 

hadoop12 <- data.frame(project="hadoop",
                     gini="low",
                     accuracy=mean(tempor$accuracy,na.rm = TRUE), 
                     myrecall=mean(tempor$myrecall,na.rm = TRUE),
                     myprecision=mean(tempor$myprecision,na.rm = TRUE),
                     f1=mean(tempor$f1,na.rm = TRUE),
                     auc=mean(tempor$auc,na.rm = TRUE),
                     test="low")



isis12 <- data.frame(project="isis",
                       gini="high",
                       accuracy=mean(tempor$accuracy,na.rm = TRUE), 
                       myrecall=mean(tempor$myrecall,na.rm = TRUE),
                       myprecision=mean(tempor$myprecision,na.rm = TRUE),
                       f1=mean(tempor$f1,na.rm = TRUE),
                       auc=mean(tempor$auc,na.rm = TRUE),
                       test="high")

jackrabbit12 <- data.frame(project="jackrabbit",
                      gini="low",
                      accuracy=mean(tempor$accuracy,na.rm = TRUE), 
                      myrecall=mean(tempor$myrecall,na.rm = TRUE),
                      myprecision=mean(tempor$myprecision,na.rm = TRUE),
                      f1=mean(tempor$f1,na.rm = TRUE),
                      auc=mean(tempor$auc,na.rm = TRUE),
                      test="low")

ofbiz12 <- data.frame(project="ofbiz",
                     gini="low",
                     accuracy=mean(tempor$accuracy,na.rm = TRUE), 
                     myrecall=mean(tempor$myrecall,na.rm = TRUE),
                     myprecision=mean(tempor$myprecision,na.rm = TRUE),
                     f1=mean(tempor$f1,na.rm = TRUE),
                     auc=mean(tempor$auc,na.rm = TRUE),
                     test="low")

wicket12 <- data.frame(project="wicket",
                   gini="high",
                   accuracy=mean(tempor$accuracy,na.rm = TRUE), 
                   myrecall=mean(tempor$myrecall,na.rm = TRUE),
                   myprecision=mean(tempor$myprecision,na.rm = TRUE),
                   f1=mean(tempor$f1,na.rm = TRUE),
                   auc=mean(tempor$auc,na.rm = TRUE),
                   test="high")

portability <- data.frame(train=character(),
                     test=character(), 
                     gini=character(),
                     accuracy=double(), 
                     myrecall=double(),
                     myprecision=double(),
                     f1=double(),
                     auc=double(),
                     test=character()) 


portability=rbind(portability,camel12)
portability=rbind(portability,hadoop12)
portability=rbind(portability,isis12)
portability=rbind(portability,jackrabbit12)
portability=rbind(portability,ofbiz12)
portability=rbind(portability,wicket12)

#portability$test<- c("low", "high", "high", "low", "high")


write.csv(portability, file = "portability.csv")

##Barplots
qplot(project, data=portability,geom="bar", weight=f1/2,xlab='',ylab="F1",fill=project)+
  facet_wrap(~gini,scale="free")+
  coord_cartesian(ylim=c(0,0.6))+
  theme(text = element_text(size=30))+
  theme(axis.text.x=element_text(angle=90))+
  guides(fill=FALSE)

qplot(project, data=portability,geom="bar", weight=auc/2,xlab='',ylab="AUC",fill=project)+
  facet_wrap(~gini,scale="free")+
  coord_cartesian(ylim=c(0,1))+
  theme(text = element_text(size=30))+
  theme(axis.text.x=element_text(angle=90))+
  guides(fill=FALSE)
##Boxplot
qplot(x=gini,y=f1,ylab="F1",fill=gini,data = portability,geom='boxplot',xlab='')+
  coord_cartesian(ylim=c(0,0.3))+
  facet_wrap(~gini,scale="free")+
  theme(text = element_text(size=30),axis.text.x=element_blank())+
  guides(fill=FALSE)


qplot(x=gini,y=auc,ylab="AUC",fill=gini,data = portability,geom='boxplot',xlab='')+
  coord_cartesian(ylim=c(0,1))+
  facet_wrap(~gini,scale="free")+
  theme(text = element_text(size=30),axis.text.x=element_blank())+
  guides(fill=FALSE)

#portability=read.csv("portability.csv",sep=",",header = TRUE)


qplot(x=id,y=auc,ylab="AUC",fill=gini,data = portability,geom='boxplot',xlab='')+
  coord_cartesian(ylim=c(0,1))+
  facet_wrap(~gini,scale="free")+
  theme(text = element_text(size=30))+
  theme(axis.text.x=element_text(angle=90))+
  guides(fill=FALSE)

qplot(x=id,y=f1,ylab="F1",fill=gini,data = portability,geom='boxplot',xlab='')+
  coord_cartesian(ylim=c(0,1))+
  facet_wrap(~gini,scale="free")+
  theme(text = element_text(size=30))+
  theme(axis.text.x=element_text(angle=90))+
  guides(fill=FALSE)

portability$id[portability$gini=="High Gini"& portability$test=="Low Gini"]="3"
portability$id[portability$gini=="High Gini"& portability$test=="Low Gini"]="1"
portability$id[portability$gini=="Low Gini"& portability$test=="Low Gini"]="2"
portability$id[portability$gini=="Low Gini"& portability$test=="High Gini"]="4"

portability$id[!(portability$gini=="Low Gini"& portability$test=="Low Gini")]="0"



portability$id[portability$id==1]="High to High"
portability$id[portability$id==2]="Low to Low"
portability$id[portability$id==3]="High to Low"
portability$id[portability$id==4]="Low to High"