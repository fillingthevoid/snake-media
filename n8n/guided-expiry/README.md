# Guided expiry controls

Both interfaces use the existing retention preview and confirmation workflows.
`/extend` lists the caller's requested titles, then offers 7 or 30 days and a
final confirmation. `/keep` lists titles and asks for confirmation of permanent
retention. Custom durations still use `/extend <title> 14 days`.

Titles match without case, accent or punctuation differences. `&` and `and`
match each other. Exact normalized titles take priority; ambiguous matches offer
buttons. Choices are stored in the existing pending table and expire after
30 minutes. Ownership and chat checks apply to every click. Atomic claims guard
against concurrent actions. The amendment coordinator rechecks ownership before
changing retention. No new downloads occur.

`build.py` consumes a fresh private workflow export and patches only four
workflows: both entry workflows, retention preview and media confirmation. It
preserves credential bindings, table references and graph connections; historical
templates must not be used to replace a current live workflow.

```sh
python n8n/guided-expiry/build.py /private/current.json /private/staged
node --test tests/guided-expiry.test.cjs tests/retention-controls.test.cjs
```

The Discord transport also needs the matching `/extend`, `/keep` command entries
and bounded action identifiers from this version. Deploy those changes together.
Private exports and staged workflows must stay outside the public repository.
