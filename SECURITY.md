# Security

Report vulnerabilities privately through the repository's security advisory
feature if enabled. Public issues should contain only sanitized reproductions.
Do not attach tokens, environment files, database copies, private workflow exports
or unredacted logs. Rotate an exposed credential promptly; deleting it from the
latest file does not remove it from Git history.

The bot uses an outbound Discord Gateway connection and private authenticated
n8n webhooks. Access checks apply to immutable user and channel IDs. The optional
authorization helper checks the socket peer UID and configured owner, and the
container has no access to the host environment file or Docker socket.

Workflow templates contain example configuration only. Review authentication,
native table references, child-workflow permissions and retention previews before
activation. Keep generated production exports outside this repository.
