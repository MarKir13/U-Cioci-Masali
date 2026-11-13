// Mailpit, where the shop sends its e-mails (W3). MAILPIT_URL set to an empty value turns the checks off,
// for a shop whose Mailpit the tests cannot reach (the Stage 2 cluster may not expose it).
export const mailpitUrl = process.env.MAILPIT_URL ?? "http://localhost:8025";

// Messages sent to one address, newest first (Mailpit search API)
export async function messagesTo(request, address) {
  const response = await request.get(`${mailpitUrl}/api/v1/search`, {
    params: { query: `to:"${address}"` },
  });
  if (!response.ok()) {
    throw new Error(`Mailpit search failed: HTTP ${response.status()}`);
  }
  const { messages } = await response.json();
  return messages;
}
