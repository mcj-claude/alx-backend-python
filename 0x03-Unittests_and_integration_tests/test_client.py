#!/usr/bin/env python3
"""Unit tests for client module."""

import unittest
from typing import Dict, Any
from parameterized import parameterized, parameterized_class
from client import GithubOrgClient
from unittest.mock import patch, Mock
from fixtures import org_payload, repos_payload, expected_repos, apache2_repos


class TestGithubOrgClient(unittest.TestCase):
    """Test class for GithubOrgClient."""

    @parameterized.expand([
        ("google",),
        ("abc",),
    ])
    @patch('client.get_json')
    def test_org(self, org_name: str, mock_get_json: Mock) -> None:
        """Test org property returns expected value."""
        mock_get_json.return_value = {"name": org_name}
        client = GithubOrgClient(org_name)
        result = client.org
        self.assertEqual(result, {"name": org_name})
        mock_get_json.assert_called_once_with(
            f"https://api.github.com/orgs/{org_name}"
        )

    def test_public_repos_url(self) -> None:
        """Test _public_repos_url property returns expected URL."""
        with patch('client.GithubOrgClient.org') as mock_org:
            mock_org.return_value = {
                "repos_url": "https://api.github.com/orgs/test/repos"
            }
            client = GithubOrgClient("test")
            result = client._public_repos_url
            self.assertEqual(result, "https://api.github.com/orgs/test/repos")

    def test_public_repos(self) -> None:
        """Test public_repos returns expected repos."""
        with patch('client.GithubOrgClient.repos_payload') as mock_repos_payload:
            mock_repos_payload.return_value = repos_payload
            client = GithubOrgClient("google")
            result = client.public_repos
            self.assertEqual(result, expected_repos)

    def test_public_repos_with_license(self) -> None:
        """Test public_repos with license filter."""
        with patch('client.GithubOrgClient.repos_payload') as mock_repos_payload:
            mock_repos_payload.return_value = repos_payload
            client = GithubOrgClient("google")
            result = client.public_repos(license="apache-2.0")
            self.assertEqual(result, apache2_repos)

    @parameterized.expand([
        (
            {"license": {"key": "my_license"}},
            "my_license",
            True,
        ),
        (
            {"license": {"key": "other_license"}},
            "my_license",
            False,
        ),
    ])
    def test_has_license(self, repo: Dict[str, Any], license_key: str, expected: bool) -> None:
        """Test has_license returns True if license matches."""
        client = GithubOrgClient("test")
        result = client.has_license(repo, license_key)
        self.assertEqual(result, expected)


@parameterized_class([
    {
        "org_payload": org_payload,
        "repos_payload": repos_payload,
        "expected_repos": expected_repos,
    },
    {
        "org_payload": apache2_repos,
        "repos_payload": repos_payload,
        "expected_repos": expected_repos,
    },  # assuming apache2_repos is similar
])
class TestIntegrationGithubOrgClient(unittest.TestCase):
    """Integration test class for GithubOrgClient."""

    @classmethod
    def setUpClass(cls) -> None:
        """Set up class with mocked requests."""
        cls.get_patcher = patch('client.requests.get')
        cls.mock_get = cls.get_patcher.start()
        cls.mock_get.side_effect = lambda url: Mock(
            json=lambda: cls.org_payload if "orgs" in url else cls.repos_payload
        )

    @classmethod
    def tearDownClass(cls) -> None:
        """Tear down class by stopping patcher."""
        cls.get_patcher.stop()

    def test_public_repos(self) -> None:
        """Test public_repos integration."""
        client = GithubOrgClient("test")
        self.assertEqual(client.public_repos, self.expected_repos)
