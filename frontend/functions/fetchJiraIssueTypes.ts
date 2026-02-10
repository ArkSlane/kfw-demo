/**
 * Fetch issue types from Jira instance
 */
export default async function fetchJiraIssueTypes({ jira_url, email, api_token }) {
  try {
    const baseUrl = jira_url.endsWith('/') ? jira_url.slice(0, -1) : jira_url;
    const authToken = btoa(`${email}:${api_token}`);
    
    const response = await fetch(`${baseUrl}/rest/api/3/issuetype`, {
      method: 'GET',
      headers: {
        'Authorization': `Basic ${authToken}`,
        'Accept': 'application/json',
        'Content-Type': 'application/json'
      }
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`Jira API error: ${response.status} - ${errorText}`);
    }

    const issueTypes = await response.json();
    
    const formattedIssueTypes = issueTypes.map(it => ({
      id: it.id,
      name: it.name,
      description: it.description || '',
      subtask: it.subtask || false,
      iconUrl: it.iconUrl || ''
    }));

    return {
      success: true,
      issue_types: formattedIssueTypes,
      count: formattedIssueTypes.length
    };
  } catch (error) {
    return {
      success: false,
      error: error.message,
      issue_types: []
    };
  }
}