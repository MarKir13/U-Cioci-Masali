# Documentation

Documentation is in English. The exception is `AI_LOG.md`, which is in Polish because its format is set by the course requirements.

| Path | What it is for |
|---|---|
| [AI_LOG.md](AI_LOG.md) | Log of AI tool usage required by the course rules. One row per use, added by the person who used the tool, in the same PR as the code. Ends with the team reflection. |
| [adr/](adr/) | Architecture Decision Records: one file per significant decision (context, options, decision, consequences). |

## When to add what

- **Used an AI tool for a task?** Add a row to `AI_LOG.md` in the same PR and give the PR the `ai-assisted` label, describing how the result was verified.
- **Made a choice between real alternatives** that is hard to reverse or that others will ask about (e.g. how data is imported, where images are stored)? Write an ADR.
- **Anything else** worth explaining (setup details, troubleshooting) goes into a separate file here and gets a row in the table above.
