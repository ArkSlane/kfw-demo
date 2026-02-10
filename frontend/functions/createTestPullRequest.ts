/**
 * Create a test pull/merge request to verify write access
 */
export default async function createTestPullRequest({ git_provider, repository_url, username, access_token }) {
  try {
    if (!repository_url || !access_token) {
      return {
        success: false,
        message: 'Repository URL and access token are required'
      };
    }

    const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
    const branchName = `testmaster-test-${timestamp}`;
    const commitMessage = 'Test commit from TestMaster - This PR can be safely closed';
    const prTitle = `[TEST] TestMaster Connection Test - ${new Date().toLocaleString()}`;
    const prBody = '🤖 This is an automated test pull request created by TestMaster to verify write access.\n\n✅ You can safely close or delete this PR.\n\nThis confirms that the configured credentials have permission to:\n- Create branches\n- Push commits\n- Create pull/merge requests';

    let apiBaseUrl, owner, repo, authHeader;

    if (git_provider === 'github') {
      const match = repository_url.match(/github\.com[\/:](.+?)\/(.+?)(\.git)?$/);
      if (!match) {
        return { success: false, message: 'Invalid GitHub repository URL' };
      }
      [, owner, repo] = match;
      repo = repo.replace('.git', '');
      apiBaseUrl = 'https://api.github.com';
      authHeader = `Bearer ${access_token}`;

      const repoResponse = await fetch(`${apiBaseUrl}/repos/${owner}/${repo}`, {
        headers: { 'Authorization': authHeader, 'Accept': 'application/vnd.github+json' }
      });
      if (!repoResponse.ok) {
        return { success: false, message: 'Failed to access repository' };
      }
      const repoData = await repoResponse.json();
      const defaultBranch = repoData.default_branch;

      const refResponse = await fetch(`${apiBaseUrl}/repos/${owner}/${repo}/git/ref/heads/${defaultBranch}`, {
        headers: { 'Authorization': authHeader, 'Accept': 'application/vnd.github+json' }
      });
      if (!refResponse.ok) {
        return { success: false, message: 'Failed to get default branch reference' };
      }
      const refData = await refResponse.json();
      const sha = refData.object.sha;

      const createBranchResponse = await fetch(`${apiBaseUrl}/repos/${owner}/${repo}/git/refs`, {
        method: 'POST',
        headers: {
          'Authorization': authHeader,
          'Accept': 'application/vnd.github+json',
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          ref: `refs/heads/${branchName}`,
          sha: sha
        })
      });
      if (!createBranchResponse.ok) {
        const error = await createBranchResponse.text();
        return { success: false, message: `Failed to create branch: ${error}` };
      }

      const fileContent = btoa(`# TestMaster Connection Test\n\nTimestamp: ${new Date().toISOString()}\n\nThis file was created automatically to test write access.`);
      const createFileResponse = await fetch(`${apiBaseUrl}/repos/${owner}/${repo}/contents/testmaster-test-${timestamp}.md`, {
        method: 'PUT',
        headers: {
          'Authorization': authHeader,
          'Accept': 'application/vnd.github+json',
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          message: commitMessage,
          content: fileContent,
          branch: branchName
        })
      });
      if (!createFileResponse.ok) {
        const error = await createFileResponse.text();
        return { success: false, message: `Failed to create test file: ${error}` };
      }

      const prResponse = await fetch(`${apiBaseUrl}/repos/${owner}/${repo}/pulls`, {
        method: 'POST',
        headers: {
          'Authorization': authHeader,
          'Accept': 'application/vnd.github+json',
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          title: prTitle,
          body: prBody,
          head: branchName,
          base: defaultBranch
        })
      });

      if (!prResponse.ok) {
        const error = await prResponse.text();
        return { success: false, message: `Failed to create pull request: ${error}` };
      }

      const prData = await prResponse.json();
      return {
        success: true,
        message: 'Test pull request created successfully! ✅',
        pr_url: prData.html_url,
        pr_number: prData.number,
        branch_name: branchName
      };

    } else if (git_provider === 'gitlab') {
      const match = repository_url.match(/gitlab\.com[\/:](.+)/);
      if (!match) {
        return { success: false, message: 'Invalid GitLab repository URL' };
      }
      const projectPath = encodeURIComponent(match[1].replace('.git', ''));
      apiBaseUrl = 'https://gitlab.com/api/v4';
      authHeader = `Bearer ${access_token}`;

      const projectResponse = await fetch(`${apiBaseUrl}/projects/${projectPath}`, {
        headers: { 'Authorization': authHeader }
      });
      if (!projectResponse.ok) {
        return { success: false, message: 'Failed to access project' };
      }
      const projectData = await projectResponse.json();
      const projectId = projectData.id;
      const defaultBranch = projectData.default_branch;

      const createBranchResponse = await fetch(`${apiBaseUrl}/projects/${projectId}/repository/branches?branch=${branchName}&ref=${defaultBranch}`, {
        method: 'POST',
        headers: { 'Authorization': authHeader }
      });
      if (!createBranchResponse.ok) {
        const error = await createBranchResponse.text();
        return { success: false, message: `Failed to create branch: ${error}` };
      }

      const createFileResponse = await fetch(`${apiBaseUrl}/projects/${projectId}/repository/files/testmaster-test-${timestamp}.md`, {
        method: 'POST',
        headers: {
          'Authorization': authHeader,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          branch: branchName,
          content: `# TestMaster Connection Test\n\nTimestamp: ${new Date().toISOString()}\n\nThis file was created automatically to test write access.`,
          commit_message: commitMessage
        })
      });
      if (!createFileResponse.ok) {
        const error = await createFileResponse.text();
        return { success: false, message: `Failed to create test file: ${error}` };
      }

      const mrResponse = await fetch(`${apiBaseUrl}/projects/${projectId}/merge_requests`, {
        method: 'POST',
        headers: {
          'Authorization': authHeader,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          source_branch: branchName,
          target_branch: defaultBranch,
          title: prTitle,
          description: prBody
        })
      });

      if (!mrResponse.ok) {
        const error = await mrResponse.text();
        return { success: false, message: `Failed to create merge request: ${error}` };
      }

      const mrData = await mrResponse.json();
      return {
        success: true,
        message: 'Test merge request created successfully! ✅',
        pr_url: mrData.web_url,
        pr_number: mrData.iid,
        branch_name: branchName
      };

    } else {
      return {
        success: false,
        message: 'Test PR creation is only supported for GitHub and GitLab'
      };
    }

  } catch (error) {
    return {
      success: false,
      message: `Test PR creation failed: ${error.message}`
    };
  }
}