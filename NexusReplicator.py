import requests, argparse, datetime, os, json, glob
from dateutil.parser import parse
from collections import defaultdict

class nexusReplicator():
    URL = None
    PASSWD = None
    REPO = None
    PATH = None
    DATEBEGININP = None
    DATEB = None
    headers = {
        'accept': 'application/json',
    }   


    def __init__(self):
        self.parser = argparse.ArgumentParser(description='Example usage: python3 test.py -u http://localhost:8081 -p 1234 -r RepositoryName')
        self.parser.add_argument('--url','-u', nargs='?', const='CONST', required=True)
        self.parser.add_argument('--passwd','-p', required=True)
        self.parser.add_argument('--repo','-r', required=True)
        self.args = self.parser.parse_args()
        self.URL = self.args.url[:-1] if  self.args.url[-1] == '/' else self.args.url
        self.PASSWD = self.args.passwd
        self.REPO = self.args.repo
        
    def exportArtifact(self):
        print("DO NOT FORGET TO PUT DOTS BETWEEN DAY, MONTH, YEAR !!")
        self.DATEBEGININP = input("Type start date as DD.MM.YYYY  : ").split('.')
        self.DATEB = datetime.datetime(int(self.DATEBEGININP[2]), int(self.DATEBEGININP[1]), int(self.DATEBEGININP[0]))
        params = {
            'repository': self.REPO
        }   
        #Rest api for get component and getting repository.
        response = requests.get(f'{self.URL}/service/rest/v1/components', params=params, headers=self.headers, auth=('admin', self.PASSWD))
        items = response.json().get("items")
        attrList = []
        paths = []
        responses = []

        for item in items:         
            for asset in item['assets']:
                if(self.DATEB < parse(asset['lastModified']).replace(tzinfo=None) and item.get("name") != "."):
                    responses.append(json.dumps(item, indent=3))
                    attrList.append((item.get("name").split("/")[-1], asset.get("checksum").get("sha1"), asset.get("lastModified"), asset.get("downloadUrl")))
        getRepoSettings = requests.get(f'{self.URL}/service/rest/v1/repositorySettings', headers=self.headers, auth=('admin', self.PASSWD))
        i = 0
        folderPath = f'{os.getcwd()}/FolderToUpload/{self.REPO}'
        os.makedirs(folderPath, exist_ok=True)
        with open(f'{folderPath}/arguments', 'w') as f:
            f.write(f'URL: {self.URL}\nPassword: {self.PASSWD}\nRepository: {self.REPO}\nBeginning Time: {self.DATEB}\nEnd Time: {datetime.datetime.now()}\n')
        with open(f'{folderPath}/RepositorySettings', 'w') as f:
            for settings in getRepoSettings.json():
                if(settings.get("name") == self.REPO):
                    f.write(json.dumps(settings, indent=3))
        for key in attrList: 
            writePath = f'{folderPath}/{key[1]}'
            os.makedirs(writePath, exist_ok=True)
            r = requests.get(key[3], auth=('admin', self.PASSWD), allow_redirects=True)
            #copying requested artifact 
            with open(f'{writePath}/{key[0]}', 'wb') as f:
                f.write(r.content)
            #copying request iself    
            with open(f'{writePath}/response.json', 'w') as f:
                f.write(str(responses[i]))
                i+=1
            print(f'Files related to {key[0]} are copied to: {writePath}')

        
    def importArtifact(self):
        sourcePath = f'{os.getcwd()}/FolderToUpload'
        filesDepth3 = glob.glob(f'{sourcePath}/*')
        dirsDepth3 = filter(lambda f: os.path.isdir(f), filesDepth3)
        attrDict = defaultdict(lambda : defaultdict(dict))
        for i in dirsDepth3:
            for root,d_names, f_names in os.walk(sourcePath):
                for f in f_names:
                    if("response.json" in f):
                        responseJson= json.loads(open(os.path.join(root, f), "r").read())
                        attrDict[responseJson.get("repository")][responseJson.get("assets")[0].get("checksum").get("sha1")]["name"] = responseJson.get("name").split("/")[-1]
                        attrDict[responseJson.get("repository")][responseJson.get("assets")[0].get("checksum").get("sha1")]["group"] = responseJson.get("group")                                 
            try:
                f = json.loads(open(f'{i}/RepositorySettings', "r").read())
                f.pop("url", None)
                f.pop("format", None)
                f.pop("type", None)
                f['storage']['blobStoreName'] = 'default'
                json_data = f
                response = requests.post(f'{self.URL}/service/rest/v1/repositories/raw/hosted', headers=self.headers, json=json_data, auth=('admin', self.PASSWD))
            except:
                
                pass
        for i in attrDict.keys():
            files = {}
            for idx, j in enumerate(attrDict[i].keys()):
                files["raw.directory"] = ((None, attrDict[i][j].get("group")))
                files[f'raw.asset{idx+1}'] = (open(f'{sourcePath}/{i}/{j}/{attrDict[i][j].get("name")}', 'rb'))
                files[f'raw.asset{idx+1}.filename'] = ((None, attrDict[i][j].get("name")))
            params = {
                'repository': i,
            }
            response = requests.post(f'{self.URL}/service/rest/v1/components',params=params, headers=self.headers, files=files, auth=('admin', self.PASSWD))
            if(200 <= response.status_code and response.status_code < 300):
                for x in attrDict[i].keys():
                    print(f'Succesfully imported related files: {attrDict[i][x].get("name")}')
            else:
                print(f'An error occurred. Response code {response.status_code} {response.content}')


if __name__ == '__main__':  
    mode = input("Please choose nexus replication mode import-export (i/e) : ")
    if(mode == 'i'):
        n = nexusReplicator().importArtifact()
    else:
        n = nexusReplicator().exportArtifact()