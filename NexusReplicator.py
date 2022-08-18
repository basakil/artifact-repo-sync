import requests, argparse, datetime, os, json, glob
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
                        \nFor export mode: python3 NexusReplicator.py -u http://localhost:8081 -p 1234 -e -r exampleRepositoryName -d 01.01.2022 """, formatter_class=argparse.RawTextHelpFormatter)
        self.parser.add_argument('-u', metavar="URL", required=True, help = 'URL of nexus instance with port number.')
        self.parser.add_argument('-p', metavar="PASSWORD", required=True, help='Type nexus password of instance.')
        self.parser.add_argument('-r', metavar="REPOSITORY", help='Type repository name you want to export. (Case sensitive)')
        self.parser.add_argument('-d', metavar="DATE", help='Type begining date of exporting artifacts.')
        self.parser.add_argument('-i', action='store_true', help='Import mode.')
        self.parser.add_argument('-e', action='store_true', help='Export mode.')

        self.args = self.parser.parse_args()
        self.URL = self.args.u[:-1] if  self.args.u[-1] == '/' else self.args.u
        self.PASSWD = self.args.p
        self.REPO = self.args.r
        
        # Checking proper usage of arguments.
        if(self.args.i and not self.args.e and not self.args.d and not self.args.r):
            self.importArtifact()
        elif(self.args.e and not self.args.i and self.args.d and self.args.r):
            self.DATEB = datetime.datetime(int(self.args.d.split('.')[2]), int(self.args.d.split('.')[1]), int(self.args.d.split('.')[0]))
            self.exportArtifact()
        else:
            self.parser.print_help()

    def exportArtifact(self):
        params = {
            'repository': self.REPO
        }  

        # Rest API for getting component with given repository.
        response = requests.get(f'{self.URL}/service/rest/v1/components', params=params, headers=self.headers, auth=('admin', self.PASSWD))
        
        if(response.status_code == 404):
            print(f'Repository {self.REPO} not found in {self.URL}/#admin/repository/repositories')
            return
        # Parsing JSON response of getComponentAPI according to last modified date and. 
        # Storing components' name, sha1, lastModified, and downloadUrl in attrList. 
        # Storing parsed response in responses list.
        items = response.json().get("items")
        attrList = []
        responses = []
        for item in items:         
            for asset in item['assets']:
                if(self.DATEB < parse(asset['lastModified']).replace(tzinfo=None) and item.get("name") != "."):
                    responses.append(json.dumps(item, indent=3))
                    attrList.append((item.get("name").split("/")[-1], asset.get("checksum").get("sha1"), asset.get("lastModified"), asset.get("downloadUrl")))
        
        # REST API for storing repository settings
        getRepoSettings = requests.get(f'{self.URL}/service/rest/v1/repositorySettings', headers=self.headers, auth=('admin', self.PASSWD))
        
        # Directory creation for exporting artifacts.
        folderPath = f'{os.getcwd()}/FolderToUpload/{self.REPO}'
        os.makedirs(folderPath, exist_ok=True)
        
        # Writing arguments that NexusReplicator has been executed.
        with open(f'{folderPath}/arguments', 'w') as f:
            f.write(f'URL: {self.URL}\nPassword: {self.PASSWD}\nRepository: {self.REPO}\nBeginning Time: {self.DATEB}\nEnd Time: {datetime.datetime.now()}\n')
        
        # Writing repository settings
        with open(f'{folderPath}/RepositorySettings', 'w') as f:
            for settings in getRepoSettings.json():
                if(settings.get("name") == self.REPO):
                    f.write(json.dumps(settings, indent=3))
        
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

if __name__ == '__main__':  
    n = nexusReplicator()
