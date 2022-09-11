**Welcome to our Nexus Project's Documentation!**&#x20;

This is our source of truth for all information related to our development and research process, includes the struggles that we have encountered.


<br>

# Project Goal

This project aims to synchronize artifacts between two separate Nexus instances in an air-gapped environment.  Here are the features this project requires:

- [x] Export
  - [x] All at once
  - [x] Raw Proxy Repositories
  - [x] Raw Hosted Repositories
  - [x] Raw Group Repositories
  - [x] Different Docker Layers
- [ ] Import
  - [x] Raw Artifacts
  - [ ] Docker Registries


<br>

# What's Done So Far!

Here are the features that have been done in our project:

- Export raw proxy, hosted, group repositories according to the given date
- Export all raw repositories at once
- Export all docker repositories at once
- Import exported file into a raw hosted repository


<br>

# Alternative

Sonatype Nexus Repository replication allows you to publish artifacts to one Nexus Repository Pro instance and make them available on other instances to provide faster artifact availability across distributed teams.

With repository replication, you can manage what binaries can be replicated between two or more instances. Also, there is a JFrog's Artifactory, but at this date (11 August 2022) it's prices are even higher.

There is not any open source solution to this problem yet.

## Pricing

Nexus Repository Pro pricing is based on per users. For 75 users it costs $96 per user per month, and it is billed annually, which equals $86.400 for a year. There is not any fixed cost per user for 100+ users, so Sonatype says "Contact Us".


<br>

# REST APIs

We started to search for swagger APIs that might work for our Nexus Replicator Project.  Since our first goal was synchronizing raw repositories, we noted repository - related APIs. We wanted to get the artifacts according to the dates, therefore, we realized that the most useful API is the 'GET Component' API. In response to GET component, we have hashes of raw artifacts and their last modified date, so we can classify components of given repository according to their last modified and digests.

Used APIs are :&#x20;

- List Components
- Upload a single component
- List repositories
- Create raw hosted repository

<br>

# Structure of Nexus

At the start of this project, we took a look at local folders and the structure of Nexus. There are blobs, database (OrientDB), Apache Karaf, Jetty, logs and system files. Nexus stores repositories and files related to the artifacts in blobs. Updates OrientDB and website takes required information, like modified date or blob of the repository, from this database.


## First Thoughts

At first, we wanted to synchronize artifacts by copying blobs from one Nexus to another. In order to do that, we tried to edit OrientDB that Nexus uses. But there are numerous concerns about that.

### - Does Not Work As Intended

It is possible to change the blobstore of the repository. But it only shows this change on the website and not affects the artifacts inside of it. So, if you have file1 in the blob1 and file2 in blob2 when you change repository's blobstore from blob1 to blob2 repository will not have file2 inside of it, and it is still going to show file1.

### - It Can Change

With further updates, Sonatype can stop using OrientDB or any other change related to this can cause problems with this project. So it is not wise to rely on this solution. That's why we wanted to use APIs every possible way.


<br>

# How does it work?

## Raw Artifacts

There are export and import functions. Each function requires a URL and password from the user. 

### Export

Nexus returns a response that contains a list of components newer than the given date. Parses response JSON and stores components' attributes. At the end writes artifacts into the FolderToUpload folder by using REST API. 

### Import

Stores attributes of components according to host repositories. For example: {repo1:{sha1:{name:name1 group: group1}{sha2:{name:name2, group: group2}}}}. Formats Template JSON to create exact match with exported artifact's repository. At the end, posts components by using REST API.

## Docker Images

There are export and import functions but at the moment import function does not function fully as intended. Docker requires login to save images locally, so each function requires a URL and password from the user. 

### Export

Nexus returns a response that contains a list of components, and the program creates 2 separate folders for images newer and older than the given date. Parses JSON response of getComponentAPI according to last modified date. If images are newer than the input date, it pulls and saves new images into the NewImages folder. But, if images are older than the input date, it pulls and saves old images into the OldImages folder. Reads manifest JSONs and stores them in order to find shared layers later. Removes old images which are not needed anymore. Writes the shared layers from manifest JSONs into a file named LayersFromImages. Tars image folders which are just new layers (Delta Tar) and then removes folders.

### Import

*It does not function fully as intended. No problem to merge layers and making an image but it does not load to the docker. Since, uploading to the Nexus is also not finished.* <br>
Saves images to find shared layers into the SavedImages folder. Checks LayersFromImages file to save and copy shared layers into the Delta folders. Tars folders after shared layers are copied. Removes folders since they are not necessary anymore. Loads image tars to the Docker, but this part has got a problem.

<br>

# Why Hosted?

At the moment, Nexus does not support any other repositories to upload artifacts.

<br>

# Why it saves images while exporting?

Docker layers have different sha keys when they are saved and there is not any conventional way to read their manifests (docker manifest inspect command is an experimental feature). 


<br>

# Import Problem

Throws "error: error processing tar file(exit status 1): unexpected eof" even though the docker load command works with same tar files when it is executed from the console. In code, this command tries to be executed by subprocess and shell=True. At the moment, I (Gufran Yeşilyurt) could not find a way to load image tar files to the Docker.

<br>

# Some Optimization Ideas

Export and Import of Docker images are not optimized. It can work better if a way to search folders faster found and some reoccurring steps removed.
