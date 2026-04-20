/**
 * Standard fetch wrapper for the Bomtempo Hub Hub API.
 * Handles base URL, credentials, and common response patterns.
 */

const BASE_URL = ''; // Relative to frontend in dev (proxied) or empty in prod if served same-origin

export default async function api(endpoint: string, options: RequestInit = {}) {
  const url = endpoint.startsWith('http') ? endpoint : `${BASE_URL}${endpoint}`;
  
  const defaultOptions: RequestInit = {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
    credentials: 'include', // Important for cookie-based auth
  };

  const response = await fetch(url, defaultOptions);

  if (!response.ok) {
    const errorText = await response.text();
    let errorMessage = `API Error (${response.status}): ${response.statusText}`;
    try {
      const errorJson = JSON.parse(errorText);
      errorMessage = errorJson.detail || errorMessage;
    } catch (e) {
      if (errorText) errorMessage = errorText;
    }
    throw new Error(errorMessage);
  }

  // Handle empty responses (like 204 No Content or DELETE)
  if (response.status === 204) return null;
  
  const contentType = response.headers.get('content-type');
  if (contentType && contentType.includes('application/json')) {
    return response.json();
  }

  return response.text();
}
