---
name: pr-screenshots
description: Attach screenshots or screen recordings to a GitHub pull request, issue or comment without leaking them - uses `gh --attach`, never gists, public repos or outside image hosts. Use whenever a PR or issue should show a UI change, a before/after, a visual bug, a test failure screenshot or a demo video, especially on private repos.
---

# PR screenshots

Show UI changes on the PR itself, in a way that keeps private screenshots
private.

## The rule

Upload with `gh ... --attach` and nothing else. Never put a screenshot in a
gist, a new or existing public repo, a public bucket, a pastebin or an image
host, even "temporarily", and even if the PR "just needs a link".

**Why:** GitHub stores `--attach` uploads as ordinary comment attachments.
On a private repo, only signed-in users with access to that repo can open
them. Before `--attach` existed, agents that couldn't attach images pushed
them to public repos and gists instead, and thousands of internal
screenshots leaked that way
([The New Stack](https://thenewstack.io/coding-agents-leaked-screenshots/)).
A screenshot of a private app can show customer data, internal URLs and
tokens, so a public upload is a data leak even when the code isn't secret.

## Steps

1. **Check gh.** Run `gh --version`. You need 2.99.0 or later and push
   access to the repo. If either is missing, stop and tell the human. Don't
   fall back to another host.
2. **Capture** the images or videos (PNG, GIF, WebP, SVG, MP4, MOV or WebM)
   into a scratch directory outside the repo, for example
   `SHOTS="$TMPDIR/shots"`. That way they don't get committed by accident.
3. **Check what's in each image.** Look at every screenshot before you
   upload it. Crop or redact visible secrets, tokens, personal data and
   production records. If you can't redact something, leave that image out
   and say so in the PR.
4. **Write the body** as `$SHOTS/body.md`, next to the images. Put local
   references where the images should go. gh resolves paths in a
   `--body-file` relative to that file's directory, and replaces each
   reference to an attached file with the uploaded URL:

   ```markdown
   ## Screenshots
   | Before | After |
   |---|---|
   | ![Login before](./before.png) | ![Login after](./after.png) |
   ```

5. **Attach** every file that the body references. Pass absolute paths, and
   run gh from the repo:

   ```bash
   gh pr create --title "..." --body-file "$SHOTS/body.md" \
     --attach "$SHOTS/before.png" --attach "$SHOTS/after.png"
   gh pr edit 42 --body-file "$SHOTS/body.md" \
     --attach "$SHOTS/before.png" --attach "$SHOTS/after.png"
   gh pr comment 42 --body "Error after retry:" \
     --attach "$SHOTS/error.png#Checkout error after retry"
   ```

   The text after `#` is alt text (images only). Repeat `--attach` for each
   file, up to 50 per command. A file the body doesn't reference is appended
   at the end. The same flag works on `gh issue create|edit|comment`.
6. **Verify.** For a PR body, run `gh pr view 42 --json body`. For a comment,
   run `gh pr view 42 --json comments` (for an issue, use
   `gh issue view N --json body,comments`). Check that every image URL is a
   `github.com/user-attachments/...` link, not a local path.

## When `--attach` can't be used

Some setups only use a token with the REST or GraphQL API, such as a GitHub
App or an Action that doesn't have `gh`. The API has no upload endpoint.
Pick one of these, in order:

1. Install `gh` in that environment and call it.
2. Otherwise, write in the PR that screenshots are missing and why, and
   tell the human. Missing screenshots are better than leaked ones.
   Committing images to the repo (even on a throwaway branch) keeps them in
   git history for every clone and fork, so do that only if the human
   approves it for this task.
