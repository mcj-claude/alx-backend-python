import unittest
from parameterized import parameterized, parameterized_class
from client import GithubOrgClient
from unittest.mock import patch, Mock
from fixtures import org_payload, repos_payload, expected_repos, apache2_repos


class TestGithubOrgClient(unittest.TestCase):
    @parameterized.expand([
        ("google",),
        ("abc",),
    ])
    @patch('client.get_json')
    def test_org(self, org_name, mock_get_json):
        mock_get_json.return_value = {"name": org_name}
        client = GithubOrgClient(org_name)
        result = client.org
        self.assertEqual(result, {"name": org_name})
        mock_get_json.assert_called_once_with(f"https://api.github.com/orgs/{org_name}")

    def test_public_repos_url(self):
        with patch('client.GithubOrgClient.org') as mock_org:
            mock_org.return_value = {"repos_url": "https://api.github.com/orgs/test/repos"}
            client = GithubOrgClient("test")
            result = client._public_repos_url
            self.assertEqual(result, "https://api.github.com/orgs/test/repos")

    @patch('client.get_json')
    def test_public_repos(self, mock_get_json):
        mock_get_json.return_value = [{"name": "repo1"}, {"name": "repo2"}]
        with patch('client.GithubOrgClient._public_repos_url', new_callable=lambda: "https://api.github.com/orgs/test/repos"):
            client = GithubOrgClient("test")
            result = client.public_repos
            self.assertEqual(result, ["repo1", "repo2"])
            mock_get_json.assert_called_once_with("https://api.github.com/orgs/test/repos")

    @parameterized.expand([
        ({"license": {"key": "my_license"}}, "my_license", True),
        ({"license": {"key": "other_license"}}, "my_license", False),
    ])
    def test_has_license(self, repo, license_key, expected):
        client = GithubOrgClient("test")
        result = client.has_license(repo, license_key)
        self.assertEqual(result, expected)


@parameterized_class([
    {"org_payload": org_payload, "repos_payload": repos_payload, "expected_repos": expected_repos},
    {"org_payload": apache2_repos, "repos_payload": repos_payload, "expected_repos": expected_repos},  # assuming apache2_repos is similar
])
class TestIntegrationGithubOrgClient(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.get_patcher = patch('client.requests.get')
        cls.mock_get = cls.get_patcher.start()
        cls.mock_get.side_effect = lambda url: Mock(json=lambda: cls.org_payload if "orgs" in url else cls.repos_payload)

    @classmethod
    def tearDownClass(cls):
        cls.get_patcher.stop()

    def test_public_repos(self):
        client = GithubOrgClient("test")
        self.assertEqual(client.public_repos, self.expected_repos)