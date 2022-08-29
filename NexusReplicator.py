import requests, argparse, datetime, os, json, glob, subprocess, tarfile, shutil
from dateutil.parser import parse
from collections import defaultdict

class nexusReplicator():
    headers = {
        'accept': 'application/json',
    }   
    
    def __init__(self):
        # Initializing arguments.
        self.parser = argparse.ArgumentParser(
            description="""Example usage: 
                        \nFor import mode: python3 NexusReplicator.py -u http://localhost:8081 -p 1234 -i 
                        \nFor export mode: python3 NexusReplicator.py -u http://localhost:8081 -p 1234 -e -r exampleRepositoryName -d 01.01.2022 
                        \nFor export all mode: python3 NexusReplicator.py -u http://localhost:8081 -p 1234 -a -d 01.01.2022
                        \nFor export all docker registries: python3 NexusReplicator.py -u http://localhost:8081 -p 1234 -a -d 01.01.2022 --docker""", formatter_class=argparse.RawTextHelpFormatter)
        self.parser.add_argument('-u', metavar="URL", required=True, help = 'URL of nexus instance with port number.')
        self.parser.add_argument('-p', metavar="PASSWORD", required=True, help='Type nexus password of instance.')
        self.parser.add_argument('-r', metavar="REPOSITORY", help='Type repository name you want to export. (Case sensitive)')
        self.parser.add_argument('-d', metavar="DATE", help='Type begining date of exporting artifacts.')
        self.parser.add_argument('-i', action='store_true', help='Import mode.')
        self.parser.add_argument('-e', action='store_true', help='Export mode.')
        self.parser.add_argument('-a', action='store_true', help='Export all mode.')
        self.parser.add_argument('--docker', action='store_true', help='Export all docker images.')
        self.args = self.parser.parse_args()
        self.URL = self.args.u[:-1] if  self.args.u[-1] == '/' else self.args.u
        self.PASSWD = self.args.p
        self.REPO = self.args.r
        self.ALLCHECK = self.args.a
        self.DOCKERCHECK = self.args.docker
        self.HTTP = None
        self.MANIFESTS = []
        self.LAYERSDICT = {}
        
        # Checking proper usage of arguments.
        if(self.args.i and not self.args.e and not self.args.d and not self.args.r):
            self.importArtifact()
        elif((self.args.e and not self.args.i and self.args.d and self.args.r and not self.args.a) or (self.args.a and not self.args.r and self.args.d )):
            self.DATEB = datetime.datetime(int(self.args.d.split('.')[2]), int(self.args.d.split('.')[1]), int(self.args.d.split('.')[0]))
            self.exportArtifactHandler()
        else:
            self.parser.print_help()
    
    # To export all artifacts with -a argument.
    def exportArtifactHandler(self):  
        if(self.ALLCHECK):       
            #REST API for listing all repositories.
            responseForAll = requests.get(f'{self.URL}/service/rest/v1/repositorySettings', headers=self.headers, auth=('admin', self.PASSWD)).json()
            for repo in responseForAll:
                if(repo.get("type") != "group" and repo.get("format") != "docker" and not self.DOCKERCHECK):
                    self.REPO = repo.get("name")
                    self.exportArtifact()
                elif(repo.get("format") == "docker" and self.DOCKERCHECK):
                    self.REPO = repo.get("name")
                    self.HTTP = f'{self.URL.split(":")[1][2:]}:{str(repo.get("docker").get("httpPort"))}/'
                    self.exportDocker()
        else:
            self.exportArtifact()  
    
    def exportArtifact(self):
        self.params = {
            'repository': self.REPO
        }
        # Rest API for getting component with given repository.
        response = requests.get(f'{self.URL}/service/rest/v1/components', params=self.params, headers=self.headers, auth=('admin', self.PASSWD))
        
        if(response.status_code == 404):
            print(f'Repository {self.REPO} not found in {self.URL}/#admin/repository/repositories')
            return
        # Parsing JSON response of getComponentAPI according to last modified date and. 
        # Storing components' name, sha1, lastModified, and downloadUrl in attrList. 
        # Storing parsed response in responses list.
        items = response.json().get("items")
        if(items != [] and (len(items) == 1 and items[0].get("name")) != '.'):
            attrList = []
            responses = []
            for item in items:         
                for asset in item['assets']:
                    if(self.DATEB < parse(asset['lastModified']).replace(tzinfo=None) and item.get("name") != "."):
                        responses.append(json.dumps(item, indent=3))
                        attrList.append((item.get("name").split("/")[-1], asset.get("checksum").get("sha1"), asset.get("lastModified"), asset.get("downloadUrl")))
                
            # Directory creation for exporting artifacts.
            folderPath = f'{os.getcwd()}/FolderToUpload/{self.REPO}'
            os.makedirs(folderPath, exist_ok=True)
            
            # Writing arguments that NexusReplicator has been executed.
            with open(f'{folderPath}/arguments', 'w') as f:
                f.write(f'URL: {self.URL}\nPassword: {self.PASSWD}\nRepository: {self.REPO}\nBeginning Time: {self.DATEB}\nEnd Time: {datetime.datetime.now()}\n')
            
            i = 0
            # Writing to FolderToUpload
            for key in attrList: 
                writePath = f'{folderPath}/{key[1]}'
                os.makedirs(writePath, exist_ok=True)
                r = requests.get(key[3], auth=('admin', self.PASSWD), allow_redirects=True)
                # Copying requested artifact. 
                with open(f'{writePath}/{key[0]}', 'wb') as f:
                    f.write(r.content)
                # Copying request iself.    
                with open(f'{writePath}/response.json', 'w') as f:
                    f.write(str(responses[i]))
                    i+=1
                print(f'Files related to {key[0]} are copied to: {writePath}')

        
    def importArtifact(self):
        # Getting path of exported folder.
        sourcePath = f'{os.getcwd()}/FolderToUpload'
        
        # List of 1 depth files and folders in FolderToUpload, and filtering repository directories.
        sourceFiles = glob.glob(f'{sourcePath}/*')
        repoPaths = filter(lambda f: os.path.isdir(f), sourceFiles)

        # Initializing a 3D dictionary for attributes of responses.
        attrDict = defaultdict(lambda : defaultdict(dict))
        
        # Storing attributes of components according to host repositories. Example: {repo1:{sha1:{name:name1 group: group1}{sha2:{name:name2, group: group2}}}} 
        for i in repoPaths:
            for root,d_names, f_names in os.walk(sourcePath):
                for f in f_names:
                    if("response.json" in f):
                        responseJson= json.loads(open(os.path.join(root, f), "r").read())
                        attrDict[responseJson.get("repository")][responseJson.get("assets")[0].get("checksum").get("sha1")]["name"] = responseJson.get("name").split("/")[-1]
                        attrDict[responseJson.get("repository")][responseJson.get("assets")[0].get("checksum").get("sha1")]["group"] = responseJson.get("group")                                 
           
            # Formatting Template JSON to create exact match with exported artifact's repository.
            hostedTemplate = json.loads(open(f'{os.getcwd()}/repository-create-hosted-template.json', "r").read())
            hostedTemplate['name'] = i.split('/')[-1]

            # Posting the repository whether if it exists or not.   
            response = requests.post(f'{self.URL}/service/rest/v1/repositories/raw/hosted', headers=self.headers, json=hostedTemplate, auth=('admin', self.PASSWD))

        # Creating API files to POST components.
        for i in attrDict.keys():
            files = {}
            params = {
                'repository': i,
            }
            for j in attrDict[i].keys():
                files["raw.directory"] = ((None, attrDict[i][j].get("group")))
                files[f'raw.asset1'] = (open(f'{sourcePath}/{i}/{j}/{attrDict[i][j].get("name")}', 'rb'))
                files[f'raw.asset1.filename'] = ((None, attrDict[i][j].get("name")))
                response = requests.post(f'{self.URL}/service/rest/v1/components',params=params, headers=self.headers, files=files, auth=('admin', self.PASSWD))
            
            # Check response status.
            if(200 <= response.status_code and response.status_code < 300):
                for x in attrDict[i].keys():
                    print(f'Succesfully imported related files: {attrDict[i][x].get("name")}')
            else:
                print(f'An error occurred. Response code {response.status_code} {response.content}')


    def exportDocker(self):
        subprocess.run(["docker", "login", self.HTTP, "--username=admin", f'--password={self.PASSWD}'])
        self.params = {
            'repository': self.REPO
        }
        # Rest API for getting component with given repository.
        response = requests.get(f'{self.URL}/service/rest/v1/components', params=self.params, headers=self.headers, auth=('admin', self.PASSWD))
        
        if(response.status_code == 404):
            print(f'Repository {self.REPO} not found in {self.URL}/#admin/repository/repositories')
            return
        folderPath = f'{os.getcwd()}/DockerImages'
        os.makedirs(f'{folderPath}/NewImages', exist_ok=True)
        os.makedirs(f'{folderPath}/OldImages', exist_ok=True)
        # Parsing JSON response of getComponentAPI according to last modified date and. 
        # Storing components' name, sha1, lastModified, and downloadUrl in attrList. 
        # Storing parsed response in responses list.
        items = response.json().get("items")
        attrList = []
        oldImages = []
        if(items != [] and (len(items) == 1 and items[0].get("name")) != '.'):
            for item in items:         
                for asset in item['assets']:
                    if(self.DATEB < parse(asset['lastModified']).replace(tzinfo=None) and item.get("name") != "."):
                        newImageName = f'{self.HTTP}{item.get("name")}:{item.get("version")}'
                        newImagePath = f'{folderPath}/NewImages/{newImageName.replace("/", "-")}.tar'
                        # subprocess.run(["docker", "pull", imageName])
                        subprocess.run(["docker", "save", "-o", newImagePath, newImageName])
                        imageTar = tarfile.open(newImagePath)
                        imageTar.extractall(f'{folderPath}/NewImages/{newImageName.replace("/", "-")}')
                        os.remove(newImagePath)
                        attrList.append((item.get("name").split("/")[-1], item.get("version"), asset.get("lastModified"), newImagePath))  

                    elif(self.DATEB > parse(asset['lastModified']).replace(tzinfo=None) and item.get("name") != "."):
                        oldImageName = f'{self.HTTP}{item.get("name")}:{item.get("version")}'
                        oldImagePath = f'{folderPath}/OldImages/{oldImageName.replace("/", "-")}.tar'
                        subprocess.run(["docker", "save", "-o", oldImagePath, oldImageName])
                        imageTar = tarfile.open(oldImagePath)
                        with imageTar as tar:
                            for member in tar:
                                if member.name.endswith('manifest.json'):
                                    self.MANIFESTS.append(json.load(tar.extractfile(member)))
                                    break
                        oldImages.append((item.get("name").split("/")[-1], item.get("version"), parse(asset.get("lastModified")).replace(tzinfo=None)))
        
        shutil.rmtree(f'{folderPath}/OldImages/')
        for manifestsList in self.MANIFESTS:
            for manifests in manifestsList:
                for layers in manifests['Layers']:
                    self.LAYERSDICT[layers.split("/")[0]] = manifests['RepoTags']
            
        for root,d_names, f_names in os.walk(f'{folderPath}/NewImages'):
            for d in d_names:
                if d in self.LAYERSDICT:
                    with open(f'{root}/LayersFromImages', 'a') as f:
                        f.write(str(f'{d}:{self.LAYERSDICT[d]}\n'))
                    shutil.rmtree(f'{root}/{d}', ignore_errors=True) 
            if(root.split("/")[-2] == "NewImages"):
                tarfile.open(f'{root}.tar', "w").add(root, arcname=os.path.basename(f'{root}/'))
                shutil.rmtree(root)
                    
        
        # Ortak olan Imagelar ve Farklı olan Imagelar

# Yapılacaklar:
# -Export Ederken-
# (DONE) Girilen tarihten sonra ve önce olan imageları ayrı klasörlerde savele
# (DONE) Tarların içindeki manifest dosyalarını karşılaştırarak delta oluştur.
#       (DONE) Ortak olan imageları {sha:image} şeklinde tutabilirsin.
#       (DONE) Old Manifestlerin içindekileri klasörle kıyaslayıp aynı olanları sil 
# Delta klasörleri haricindekileri sil ve deltaları tarla
# -Import Ederken-
# Deltaları extractle
# Delta tarlarda yazan imageları savele ve gereken layerları delta'nın içine at
# Son savelenen image'ın dosyalarını sil
# Deltayı tarlayıp dockera loadla
# Loadlanan image'ı nexus'a pushla


if __name__ == '__main__':  
    n = nexusReplicator()
