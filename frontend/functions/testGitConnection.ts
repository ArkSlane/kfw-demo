/**
 * Test connection to Git repository
 */
export default async function testGitConnection({ git_provider, repository_url, username, access_token }) {
  try {
    if (!repository_url || !access_token) {
      return {
        success: false,
        message: 'Repository URL and access token are required'
      };
    }

    let apiUrl;
    let authHeader;
    
    if (git_provider === 'github') {
      const match = repository_url.match(/github\.com[\/:](.+?)\/(.+?)(\.git)?$/);
      if (!match) {
        return { success: false, message: 'Invalid GitHub repository URL' };
      }
      const [, owner, repo] = match;
      apiUrl = `https://api.github.com/repos/${owner}/${repo.replace('.git', '')}`;
      authHeader = `Bearer ${access_token}`;
      
    } else if (git_provider === 'gitlab') {
      const match = repository_url.match(/gitlab\.com[\/:](.+)/);
      if (!match) {
        return { success: false, message: 'Invalid GitLab repository URL' };
      }
      const projectPath = encodeURIComponent(match[1].replace('.git', ''));
      apiUrl = `https://gitlab.com/api/v4/projects/${projectPath}`;
      authHeader = `Bearer ${access_token}`;
      
    } else if (git_provider === 'bitbucket') {
      const match = repository_url.match(/bitbucket\.org[\/:](.+?)\/(.+?)(\.git)?$/);
      if (!match) {
        return { success: false, message: 'Invalid Bitbucket repository URL' };
      }
      const [, workspace, repo] = match;
      apiUrl = `https://api.bitbucket.org/2.0/repositories/${workspace}/${repo.replace('.git', '')}`;
      authHeader = `Bearer ${access_token}`;
      
    } else if (git_provider === 'azure_devops') {
      if (!repository_url.includes('dev.azure.com') && !repository_url.includes('visualstudio.com')) {
        return { success: false, message: 'Invalid Azure DevOps repository URL' };
      }
      return {
        success: true,
        message: 'Azure DevOps URL validated. Full connection test requires organization and project details.',
        repository_name: 'Azure DevOps Repository'
      };
      
    } else {
      return {
        success: true,
        message: 'Repository URL validated for custom provider',
        repository_name: 'Custom Git Repository'
      };
    }

    const response = await fetch(apiUrl, {
      method: 'GET',
      headers: {
        'Authorization': authHeader,
        'Accept': 'application/json',
        'User-Agent': 'TestMaster-App'
      }
    });

    if (!response.ok) {
      const errorText = await response.text();
      if (response.status === 401) {
        return { success: false, message: 'Authentication failed. Check your access token.' };
      } else if (response.status === 404) {
        return { success: false, message: 'Repository not found. Check the URL.' };
      }
      return { success: false, message: `Connection failed: ${response.status}` };
    }

    const repoData = await response.json();
    
    return {
      success: true,
      message: `Connected successfully to ${repoData.name || repoData.full_name || 'repository'}`,
      repository_name: repoData.name || repoData.full_name,
      default_branch: repoData.default_branch || repoData.mainbranch?.name || 'main',
      private: repoData.private || repoData.is_private
    };
    
  } catch (error) {
    return {
      success: false,
      message: `Connection test failed: ${error.message}`
    };
  }
}