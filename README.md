# hot-topics-mcp
[![M8ven Trust](https://m8ven.ai/badge/mcp/jayniebingyu-cyber/hot-topics-mcp)](https://m8ven.ai/mcp/jayniebingyu-cyber/hot-topics-mcp)

**Real-time trending-topic intelligence for AI agents — China (Weibo/Baidu/Zhihu) + US (Google Trends), plus HackerNews & StackExchange community intel. Zero dependencies, pure Python stdlib.**

Built for content-creation and marketing agents that need to know *what people are actually talking about right now* before they write. Battle-tested in production driving a daily automated content pipeline.

## Tools

| Tool | What it gives the agent |
|---|---|
| `get_trending` | Live hot topics from 4 sources, scored against content tracks (`亲子教育`, `AI工具`, `EN_kids`, `EN_ai`, `all`, `raw`), with a built-in sensitive-topic blacklist (death/disaster/crime/politics) so agents never draft around toxic trends |
| `get_reddit_intel` | High-engagement community threads (HackerNews + StackExchange: Parenting/Workplace/Expatriates) for GEO (Generative Engine Optimization) research — the pain points real users are asking about this week |

## Why this exists

- Chinese trending sources (Weibo/Baidu/Zhihu) are unreachable from many overseas IPs; Google Trends is unreachable from mainland China. Agents running on either side of the firewall are blind to half the internet's conversation.
- This server multi-sources with graceful degradation: any one source failing doesn't break the pipeline.

## Quick start

Requires Python 3.8+. No pip install needed.

### Claude Desktop / WorkBuddy (`mcp.json`)

```json
{
  "mcpServers": {
    "hot-topics": {
      "command": "python",
      "args": ["/absolute/path/to/server.py"]
    }
  }
}
```

Then ask your agent: *"What are today's trending topics in the AI工具 track?"* or *"Get reddit intel for the kids track and draft a post."*

### Example tool calls

```json
{"name": "get_trending", "arguments": {"track": "AI工具"}}
{"name": "get_trending", "arguments": {"track": "EN_ai", "sources": ["google_trends"]}}
{"name": "get_reddit_intel", "arguments": {"track": "poa"}}
```

## Hosted API (no install, works behind any firewall)

Don't want to run it yourself, or your network can't reach these sources? A hosted version runs 24/7 on our Singapore server — one HTTP GET, JSON back:

```
GET http://43.160.199.215/hotapi/v1/hot?track=EN_ai&key=YOUR_KEY
GET http://43.160.199.215/hotapi/v1/reddit?track=poa&key=YOUR_KEY
GET http://43.160.199.215/hotapi/v1/health
```

30-day access key: **$9** → https://niebingyu.gumroad.com/l/hot-topics-api

## Notes

- 10-minute in-memory cache per source; polite to upstreams.
- All sources are public endpoints used for research; respect each platform's terms.
- Protocol: MCP over stdio, JSON-RPC 2.0, protocol version 2024-11-05.

## License

MIT
