from urllib import request
from bs4 import BeautifulSoup

class Updater(object):

    def __init__(self, owner: str, repository: str):
        self.owner = owner
        self.repo = repository
        self.gitReleases = 'https://github.com/{}/{}/releases'

    def request_release_data(self):
        """ Returns soup data of the repository releases tab """
        with request.urlopen(self.gitReleases.format(self.owner, self.repo)) as response:
            html = response.read()
        return html

    def get_newest_version(self) -> tuple:
        """ Returns newest release version """
        try:
            response = self.request_release_data()
            soup = BeautifulSoup(response, 'html.parser')
            return soup.find('span', {'class': 'css-truncate-target'}).get_text(strip=True), True
        except request.HTTPError as e:
            return f'HTTP request failed with error code ({e.code})', False
        except request.URLError:
            return 'Request failed, ensure you have a working internet connection and try again', False