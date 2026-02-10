/**
 * Test connection to Jira instance
 */
export default async function testJiraConnection({ jira_url, email, api_token }) {
  try {
    const baseUrl = jira_url.endsWith('/') ? jira_url.slice(0, -1) : jira_url;
    const authToken = btoa(`${email}:${api_token}`);
    
    const response = await fetch(`${baseUrl}/rest/api/3/myself`, {
      method: 'GET',
      headers: {
        'Authorization': `Basic ${authToken}`,
        'Accept': 'application/json',
        'Content-Type': 'application/json'
      }
    });

    if (!response.ok) {
      const errorText = await response.text();
      return {
        success: false,
        message: `Connection failed: ${response.status} - ${errorText}`
      };
    }

    const userData = await response.json();
    
    return {
      success: true,
      message: `Connected successfully as ${userData.displayName || userData.emailAddress}`,
      accountId: userData.accountId,
      displayName: userData.displayName
    };
  } catch (error) {
    return {
      success: false,
      message: `Connection failed: ${error.message}`
    };
  }
}