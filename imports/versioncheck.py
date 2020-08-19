import requests
from bs4 import BeautifulSoup

class Updater:

    def __init__(self, owner: str, repository: str):
        self.owner = owner
        self.repo = repository
        self.gitReleases = 'https://github.com/{}/{}/releases'

    def request_release_data(self):
        '''Returns "soup" data of the repository releases tab'''
        return requests.get(self.gitReleases.format(self.owner, self.repo))

    def get_newest_version(self):
        '''Returns newest release version'''
        try:
            response = self.request_release_data()
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            return soup.find('span', {'class': 'css-truncate-target'}).get_text(strip=True), True
        except requests.HTTPError as e:
            return f'HTTP request failed with error code ({response.status_code})', False
        except requests.ConnectionError:
            return 'Request failed, ensure you have a working internet connection and try again', False