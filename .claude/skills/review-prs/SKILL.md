---
name: review-prs
description: Review the open PRs waiting for your review and get a paste-ready GitHub review comment for each. One agent per PR in its own worktree checks requirements, AGENTS.md rules, bugs, security and scalability; shop PRs are also built and run, one at a time. Posts nothing.
argument-hint: "[PR numbers, e.g. 66 67]"
disable-model-invocation: true
---

# Review PRs waiting for your review

You are the orchestrator. You pick the PRs, give each one to its own review agent, hand out the
single Docker slot for runtime checks, and collect the finished review comments for the user.

The user does all GitHub work. Neither you nor any agent posts reviews or comments, approves,
requests changes, merges, pushes, labels or re-requests anything. The output is text the user pastes.

Files in this skill:

- `reviewer-brief.md`: what each review agent does and the exact shape of its answer.
- `runtime-checks.md`: how an agent builds and runs the shop for one PR (phase 2).

## 1. Preconditions

Run from the repository root (Git Bash):

```sh
gh auth status
docker info --format '{{.ServerVersion}}'
git fetch origin --prune
```

- If `gh` is not logged in, stop and tell the user.
- If Docker is not running, ask the user to start Docker Desktop. If they decline, continue with
  static review only and say in every review that runtime checks were not done. The static checks
  also use Docker images (linters, pytest), so mention that those are skipped too.

## 2. Pick the PRs

A PR is picked when it is open, not a draft, you are a requested reviewer, and its review decision is
not `APPROVED` (so `REVIEW_REQUIRED` or `CHANGES_REQUESTED`). GitHub removes you from the requested
reviewers once you submit a review and puts you back when the author re-requests one, so this also
picks up re-reviews.

```sh
gh pr list --state open --search "review-requested:@me" \
  --json number,title,author,headRefName,headRefOid,isDraft,reviewDecision,url \
  --jq '.[] | select(.isDraft | not) | select(.reviewDecision != "APPROVED")
        | "\(.number)\t\(.headRefOid)\t\(.author.login)\t\(.reviewDecision)\t\(.title)"'
```

PR numbers given with the command: `$ARGUMENTS`. If there are any, review exactly those instead,
whatever the filter says; if it is empty, use the filter. If nothing is picked, say so and stop. Otherwise list the picked PRs (number, author,
title, decision) in one short message and go on without waiting for an answer.

## 3. One worktree per PR

Each agent reviews its own checkout at the PR's head commit, so agents never share a working tree.
Worktrees live in `.claude/worktrees/` (gitignored). For each picked PR `<N>`:

```sh
git fetch origin "pull/<N>/head"
git worktree remove --force ".claude/worktrees/review-pr-<N>" 2>/dev/null || true
git worktree add --detach ".claude/worktrees/review-pr-<N>" FETCH_HEAD
git -C ".claude/worktrees/review-pr-<N>" rev-parse HEAD   # must equal headRefOid from step 2
```

`pull/<N>/head` also works for PRs from forks. Do not use the Agent tool's `isolation: "worktree"`.
Phase 2 needs a fixed path that outlives the first answer.

## 4. Phase 1: static review, all PRs in parallel

Start one `general-purpose` agent per PR, all in the same message (at most 4 at a time; start the rest
as slots free up). Give each agent a name such as `review-pr-<N>` so you can message it later. Prompt:

```
Review PR #<N> "<title>" by @<author> (<url>).
Worktree (PR head <headRefOid>): <absolute repo path>/.claude/worktrees/review-pr-<N>
Repository root: <absolute repo path>
Reviewer (the user, posting the review): @<your gh login>

Read <absolute repo path>/.claude/skills/review-prs/reviewer-brief.md and follow it exactly.
This is phase 1: static review and offline checks only. Do NOT start the shop.
Answer in the format the brief defines.
```

Every agent works only inside its own worktree. It reads the repository's `AGENTS.md` from there,
because the PR may change it.

## 5. Phase 2: runtime checks, one PR at a time

The shop needs ports, several GB of images and minutes of CPU, so only one PR runs at a time. An
agent's phase 1 answer says `Runtime checks needed: yes` when the PR changes `shop/`, `deploy/`,
`tests/` or `.github/scripts/smoke-test.sh`, or when it says why it needs the running shop.

Keep a queue of those PRs in the order their phase 1 answers arrive. For the first one in the queue,
continue the same agent (load `SendMessage` with ToolSearch if it is deferred; `SendMessage` to
`review-pr-<N>`):

```
You hold the Docker slot now. Do phase 2: read
<absolute repo path>/.claude/skills/review-prs/runtime-checks.md and follow it, then give your final
answer in the brief's format, with the runtime results folded into the review comment.
Tear everything down before you answer.
```

When it answers, confirm that the review project is gone (`docker compose ls --all` lists no
`review-pr-*`), then give the slot to the next PR. If continuing the agent is not possible, start a
fresh `general-purpose` agent with the same message plus the phase 1 answer pasted in.

PRs that do not need runtime checks are final after phase 1.

## 6. Check what comes back

Before showing a review to the user, read it against `reviewer-brief.md`:

- Every **Required** point names a file and line (or a PR-level fact such as a conflict) and says what
  goes wrong. Push back to the agent (`SendMessage`) on a point that is vague, unverified or plainly
  wrong instead of passing it on.
- The comment is in English, follows the format and does not mention AI, agents or this skill.
- The verdict matches the content: any Required point means `Request changes`.

## 7. Report to the user

Save each final comment to `pr-<N>-review.md` in your scratchpad directory and give the full absolute
paths. Then reply with:

1. A table: PR, author, verdict, number of Required points, number of Suggestions, runtime checked
   (yes / no / not needed), reviewed head (7 characters).
2. For each PR, in PR order: a `### PR #<N>: <title>` heading, a line `Verdict to choose on GitHub:
   <Approve | Request changes | Comment>`, then the comment in a code fence of four backticks
   tagged `markdown`, so the code blocks inside it survive and the user can copy it in one piece.
3. Anything the agents could not verify that the user should check in person before posting.

## 8. Clean up

After all agents have finished:

```sh
git worktree remove --force ".claude/worktrees/review-pr-<N>"   # for each reviewed PR
git worktree prune
docker compose ls --all          # must list no review-pr-* project
```

Leave the user's own stack (`ciocia`) and its volumes alone. Never run `down` without `-p review-pr-<N>`.
