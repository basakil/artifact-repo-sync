
This project aims to provide solutions for *synchronizing air-gapped artifact repositories* (two separate Repo instances in an air-gapped environment). The firs implementation is aimed for Nexus (OSS) repo synch.

This readme (and referenced stuff) is/are our source of truth for all things related to our development and research process, including the problems we have faced.


<br>

# Functions

The solution is implemented in two steps: (Smart) Export (the new artifacts) from the source repo and import the exported artifacts to the target repo. Here is the initial features list for this project:

- [x] Export
  - [x] All at once
  - [x] Raw Proxy Repositories
  - [x] Raw Hosted Repositories
  - [x] Raw Group Repositories
  - [x] Different Docker Layers
  - [ ] Helm Registries  
- [ ] Import
  - [x] Raw Artifacts
  - [ ] Docker Registries
  - [ ] Helm Registries

<br>


# Alternative Approaches

Sonatype Nexus _Repository Replication_ allows you to publish artifacts to one Nexus Repository Pro instance and make them available on other instances to provide faster artifact availability across distributed teams. _Nexus Repository Pro_ pricing is based on number of users. For 75 users it costs $96 per user per month, and it is billed annually, which equals $86.400 for a year.

With _Repository replication_, you can manage which artifacts can be replicated between two or more instances. Also, there is also a commercial solution for JFrog's Artifactory, but it is also a costly one, for now.

We have not encountered any (alternative) open source solution to this problem, yet.

<br>

# REST APIs

We started to search for REST APIs that might be useful to us. Since our first goal was synchronizing raw repositories, we focused on repository related APIs. We wanted to get the artifacts according to their creation/modification dates, therefore, we realized that the most useful API is the '_GET Component_' API. GET component returns hashes of raw artifacts and their last modified date, so we can classify components of a repository according to their last modified and digests.

Used (REST) APIs are :&#x20;

- List Components
- Upload a single component
- List repositories
- Create raw hosted repository

<br>

# Structure of Nexus

At the start of this project, we took a look at local folders and the (directory/storage) structure of Nexus. There are blobs, database files(s) (OrientDB), Apache Karaf file(s), Jetty file(s), log files and system files. Nexus stores repositories and files related to the artifacts in blobs and then updates OrientDB database accordingly. UI takes the required information, such as modification date or blob of the repository, from this database.


## First Thoughts

At first, we wanted to synchronize artifacts by copying blobs from one Nexus to another. In order to do that, we tried to edit OrientDB (directly/manually) database. But there are numerous concerns about that.

### - Does Not Work As Intended

It is possible to change the blobstore of the repository. But it only shows this change on the website: So, if you have file1 in the blob1 and file2 in blob2, after you change repository's blobstore from blob1 to blob2, the resulting repository will not have file2 inside of it, and it will still display file1.

### - It Can Change

With further (Nexus) updates, Sonatype can stop using OrientDB, or release any other change(s) which conflicting with our approach. So it is not wise to rely on this solution. That's why we wanted to use APIs, whenever we can.


<br>

# How does it work?

The solution is implemented as a Python (3) script/module.
## Raw Artifacts

There are export and import functions. Each function requires a URL and password from the user, as input parameters.

### Export

Nexus returns a response containing a list of components newer than the given date. Parses response JSON and stores components' attributes. At the end, it writes artifacts into the `FolderToUpload` folder by using REST API. 

### Import

Stores attributes of components. For example: `{repo1:{sha1:{name:name1 group: group1}{sha2:{name:name2, group: group2}}}}`. Formats Template JSON to match exported artifact's repository. At the end, posts components using (Nexus) REST API.

## Docker Images

There are export and import functions but at the moment import function is incomplete. Docker requires login to save images locally, so each function requires a URL and password from the user. 

### Export

Nexus returns a response that contains a list of components, and the program creates 2 separate folders for images, newer and older than the given date. Parses JSON response of getComponentAPI according to the last modification date. If images are newer than the input date, it pulls and saves new images into the NewImages folder. But, if images are older than the input date, it pulls and saves old images into the OldImages folder. Reads manifest JSONs and stores them in order to find shared layers later, then removes old images which are not needed anymore. Writes the shared layers from manifest JSONs into a file named LayersFromImages. Builds tar files for image folders which contain new layers (Delta Tar) and then removes the folders.

### Import

*It does not function fully as intended. All the steps, explained above, are functionin but `docker load` step is not functioning properly, in the script.* <br>
Saves images to find shared layers into the SavedImages folder. Checks LayersFromImages file to save and copy shared layers into the Delta folders. Builds tar folders after shared layers are copied. Removes folders since they are not necessary anymore. Loads image tars in to the Docker.

<br>

# Why Hosted?

At the moment, Nexus does not support any other repositories to upload artifacts.

<br>

# Why does it save images during export?

Docker layers have different sha keys when they are saved and there is not any conventional way to read their manifests (docker manifest inspect command is an experimental feature). 


<br>

# Import Problem

Throws "error: error processing tar file(exit status 1): unexpected eof" even though the `docker load` command works with same tar files when it is executed from the console. In code, this command is executed by `subprocess` and `shell=True`. At the moment, We could not find a way to load image tar files to the Docker and appreciate any help, related to this problem.

<br>

# Some Optimization Ideas

Export and Import of Docker images are not optimized. It can work better if a way to (quick) search folders is found and some re-occurring steps are removed.
