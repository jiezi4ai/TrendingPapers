import requests
from github import Github  # pip install PyGithub  https://github.com/PyGithub/PyGithub?tab=readme-ov-file

class GitHubKit:
    def __init__(self, github_token=None):
        self.github_token = github_token

        # Set up headers for authentication (if provided)
        self.headers = {}
        if self.github_token:
            self.headers["Authorization"] = f"token {self.github_token}"

        # set up the GitHub API client
        if self.github_token:
            self.hub = Github(self.github_token)
        else:
            self.hub = Github()  # Anonymous access

    def get_repo_readme(self, repo_url):
        """
        Retrieves the README file content from a GitHub repository using the GitHub API.
        Args:
            repo_url: The URL of the GitHub repository.
            github_token: Optional. Your GitHub personal access token for authentication.
        Returns:
            The content of the README file as a string, or None if an error occurred.
        """
        try:
            # Extract owner and repo name from the URL
            parts = repo_url.rstrip("/").split("/")
            owner = parts[-2]
            repo_name = parts[-1]

            # Construct the API URL
            api_url = f"https://api.github.com/repos/{owner}/{repo_name}/readme"

            # Make the API request
            response = requests.get(api_url, headers=self.headers)
            response.raise_for_status()  # Raise an exception for bad status codes

            # Decode the README content (it's base64 encoded)
            readme_data = response.json()
            import base64
            readme_content = base64.b64decode(readme_data["content"]).decode("utf-8")
            return readme_content

        except requests.exceptions.RequestException as e:
            print(f"Error fetching README: {e}")
            return None
        except (KeyError, ValueError) as e:
            print(f"Error decoding README: {e}")
            return None

    def search_repo(self, query):
        """
        Searches for GitHub repositories based on a query.
        Args:
            query: The search query string.
            token: Your GitHub Personal Access Token (optional but recommended).
        Returns:
            A list of PyGithub Repository objects matching the query.
        """
        try:
            repositories = self.hub.search_repositories(query=query)
            return repositories
        except Exception as e:
            print(f"Error: {e}")
            return None